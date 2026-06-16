"""Background Task Worker for PKOS Ingest Pipeline.

Provides a single-threaded background worker that consumes tasks
from an in-memory queue and processes them through the pipeline.
"""

import queue
import threading
from typing import Optional


class TaskWorker:
    """Background task worker — single-threaded queue consumer.

    Uses threading.Event (not a bool flag) for cross-thread
    visibility via the memory barrier guarantee.

    Accepts task tuples of (task_id, raw_text, file_path) where
    raw_text and file_path are optional.

    When enabled=False, start() is a no-op — useful when the
    worker is disabled via configuration.
    """

    def __init__(
        self,
        pipeline: object,
        enabled: bool = True,
        poll_interval: float = 1.0,
    ):
        self.pipeline = pipeline
        self.enabled = enabled
        self.poll_interval = poll_interval
        self.queue: queue.Queue[tuple[str, Optional[str], Optional[str]]] = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._running = threading.Event()

    def start(self):
        """Start the worker thread.

        If enabled is False, this is a no-op.
        """
        if not self.enabled:
            return
        self._running.set()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        """Signal the worker to stop.

        Does not join the thread — the caller should join if needed.
        """
        self._running.clear()

    def submit(self, task_id: str, raw_text: Optional[str] = None, file_path: Optional[str] = None):
        """Submit a task to the queue for processing.

        Args:
            task_id: Unique task identifier.
            raw_text: Raw text content (optional).
            file_path: Path to source file (optional).
        """
        self.queue.put((task_id, raw_text, file_path))

    def _run(self):
        """Worker main loop.

        Polls the queue with a timeout to allow responsive shutdown.
        When a task is received, it is processed through the pipeline.
        Exceptions from individual tasks are caught and logged so that
        a single failure does not crash the worker.
        """
        while self._running.is_set():
            try:
                task_id, raw_text, file_path = self.queue.get(timeout=self.poll_interval)
                self.pipeline.process_task(
                    task_id,
                    raw_text=raw_text,
                    file_path=file_path,
                )
            except queue.Empty:
                continue
            except Exception as e:
                print(f"[Worker] Error processing {task_id}: {e}")
