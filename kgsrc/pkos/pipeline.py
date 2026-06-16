"""PKOS Ingest Pipeline — state machine for processing raw materials into Vault documents."""

import time
import uuid
from pathlib import Path
from typing import Optional

from .models import IngestTask, TaskStatus, ParsedContent
from .store import IngestTaskStore
from .parsers import DocumentParser, ImageParser
from .classifier import LLMClassifier
from .vault import VaultManager
from .indexer import VaultIndexer
from .dead_letter import DeadLetterQueue
from .storage import ObjectStorage, get_default_storage


class IngestPipeline:
    """Ingest pipeline with state machine and retry logic.

    States: REGISTERED → PARSING → UNDERSTANDING → CLASSIFYING → ARCHIVING → INDEXED
                              ↓         ↓              ↓            ↓
                           FAILED ← retry(3x) → DEAD_LETTER (ARCHIVING only)
    """

    RETRY_DELAYS = [1, 3, 9]  # exponential backoff seconds
    MAX_RETRIES = 3

    def __init__(
        self,
        task_dir: str = "./pkos_tasks",
        vault_dir: str = "./kgsrc/pkos/vault",
        dlq_dir: str = "./pkos_dead_letter",
        inbox_dir: str = "./pkos_inbox",
        storage: Optional[ObjectStorage] = None,
    ):
        self.store = IngestTaskStore(storage_dir=task_dir)
        self.vault = VaultManager(vault_dir=vault_dir)
        self.dlq = DeadLetterQueue(dlq_dir=dlq_dir)
        self.classifier = LLMClassifier()
        self.indexer = VaultIndexer()
        self.storage = storage or get_default_storage()
        self.inbox_dir = Path(inbox_dir)
        self.inbox_dir.mkdir(parents=True, exist_ok=True)

    def register(
        self,
        source_type: str,
        source_url: Optional[str] = None,
        identities: list = None,
    ) -> IngestTask:
        """Register a new ingest task."""
        task_id = f"ingest-{uuid.uuid4().hex[:12]}"
        task = IngestTask(
            task_id=task_id,
            source_type=source_type,
            source_url=source_url,
            identities=identities or [],
        )
        self.store.save(task)
        return task

    def _transition(self, task: IngestTask, new_status: TaskStatus, error: str = None):
        task.status = new_status
        if error:
            task.error = error
        self.store.save(task)

    def _should_retry(self, task: IngestTask) -> bool:
        return task.retry_count < self.MAX_RETRIES

    def _do_retry(self, task: IngestTask):
        delay = self.RETRY_DELAYS[min(task.retry_count, len(self.RETRY_DELAYS) - 1)]
        task.retry_count += 1
        print(f"[Pipeline] Retrying {task.task_id} in {delay}s (attempt {task.retry_count})")
        time.sleep(delay)

    def process_task(self, task_id: str, raw_text: str = None, file_path: str = None) -> bool:
        """Process a single task through the pipeline.

        Args:
            task_id: The task ID.
            raw_text: Raw text content (for text/web sources).
            file_path: Path to the original file (for pdf/image sources).

        Returns:
            True if fully processed (INDEXED), False otherwise.
        """
        task = self.store.load(task_id)
        if not task:
            print(f"[Pipeline] Task not found: {task_id}")
            return False

        # ===== PARSING =====
        if task.status in (TaskStatus.REGISTERED, TaskStatus.FAILED):
            try:
                self._transition(task, TaskStatus.PARSING)
                parsed = self._parse(task, raw_text, file_path)
            except Exception as e:
                if self._should_retry(task):
                    self._do_retry(task)
                    self._transition(task, TaskStatus.FAILED, str(e))
                    return self.process_task(task_id, raw_text, file_path)
                else:
                    # Fallback: use filename or first line as content
                    fallback_text = raw_text or (Path(file_path).name if file_path else "")
                    parsed = ParsedContent(raw_text=fallback_text, title=fallback_text[:30])

            # ===== UNDERSTANDING =====
            try:
                self._transition(task, TaskStatus.UNDERSTANDING)
                classified = self.classifier.classify_content(parsed.raw_text, task.source_type)
                parsed.title = classified.title or parsed.title
                parsed.summary = classified.summary
            except Exception as e:
                if self._should_retry(task):
                    self._do_retry(task)
                    self._transition(task, TaskStatus.FAILED, str(e))
                    return self.process_task(task_id, raw_text, file_path)
                else:
                    parsed.summary = parsed.raw_text[:100]
                    from .classifier import ClassificationResult
                    classified = ClassificationResult(
                        title=parsed.title or "未命名文档",
                        summary=parsed.summary,
                        topic="未分类",
                    )

            # ===== CLASSIFYING =====
            try:
                self._transition(task, TaskStatus.CLASSIFYING)
                task.topic = classified.topic or "未分类"
                task.identities = classified.identities or task.identities
                task.tags = classified.tags or []
            except Exception as e:
                if self._should_retry(task):
                    self._do_retry(task)
                    self._transition(task, TaskStatus.FAILED, str(e))
                    return self.process_task(task_id, raw_text, file_path)
                else:
                    task.topic = "未分类"

            # ===== ARCHIVING =====
            try:
                self._transition(task, TaskStatus.ARCHIVING)
                vault_path = self.vault.write_document(
                    topic=task.topic,
                    title=parsed.title or "未命名文档",
                    content=parsed.raw_text,
                    source_type=task.source_type,
                    summary=parsed.summary or "",
                    identities=task.identities,
                    tags=task.tags,
                    source_url=task.source_url,
                )
                if vault_path:
                    task.vault_path = str(vault_path)
                else:
                    raise RuntimeError("Vault write returned None")
            except Exception as e:
                # ARCHIVING failure is non-retryable
                self._transition(task, TaskStatus.DEAD_LETTER, str(e))
                self.dlq.archive(task, original_path=file_path)
                return False

            self.store.save(task)

        # ===== INDEXING =====
        if task.status == TaskStatus.ARCHIVING and task.vault_path:
            try:
                indexed = self.indexer.index_document(task.vault_path)
                if indexed:
                    self._transition(task, TaskStatus.INDEXED)
                    return True
                else:
                    print(f"[Pipeline] Indexing returned False for {task_id}, keeping ARCHIVING status")
                    return False
            except Exception as e:
                print(f"[Pipeline] Indexing failed for {task_id}: {e}")
                # Indexing failure does not block; can retry in background
                return False

        return task.status == TaskStatus.INDEXED

    def _parse(self, task: IngestTask, raw_text: str = None, file_path: str = None) -> ParsedContent:
        """Parse raw content based on source type."""
        parser = DocumentParser.get_parser(task.source_type)
        if not parser:
            return ParsedContent(raw_text=raw_text or "", title="未命名文档")

        # Inject storage into ImageParser
        if isinstance(parser, ImageParser):
            parser.storage = self.storage

        if raw_text and hasattr(parser, "parse_text"):
            return parser.parse_text(raw_text)
        elif raw_text and hasattr(parser, "parse_html"):
            return parser.parse_html(raw_text, source_url=task.source_url)
        elif file_path:
            return parser.parse_file(file_path)
        else:
            return ParsedContent(raw_text=raw_text or "", title="未命名文档")

    def get_status(self, task_id: str) -> Optional[TaskStatus]:
        task = self.store.load(task_id)
        return task.status if task else None

    def get_metrics(self) -> dict:
        """Get pipeline metrics."""
        tasks = [self.store.load(tid) for tid in self.store.list_tasks()]
        tasks = [t for t in tasks if t]
        counts = {s.value: 0 for s in TaskStatus}
        for t in tasks:
            counts[t.status.value] += 1
        return {
            "ingest_tasks_total": len(tasks),
            "ingest_tasks_by_status": counts,
        }
