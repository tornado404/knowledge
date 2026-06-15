import tempfile
import shutil
from pathlib import Path
from kgsrc.pkos.dead_letter import DeadLetterQueue
from kgsrc.pkos.models import IngestTask, TaskStatus


def test_dead_letter_archive():
    tmpdir = tempfile.mkdtemp()
    try:
        dlq = DeadLetterQueue(dlq_dir=tmpdir)
        task = IngestTask(task_id="dlq-001", source_type="pdf", error="disk full")
        result = dlq.archive(task, original_path="/tmp/test.pdf")
        assert result is True

        archive_dir = Path(tmpdir) / "dlq-001"
        assert archive_dir.exists()
        assert (archive_dir / "task.json").exists()
    finally:
        shutil.rmtree(tmpdir)


def test_dead_letter_list():
    tmpdir = tempfile.mkdtemp()
    try:
        dlq = DeadLetterQueue(dlq_dir=tmpdir)
        dlq.archive(IngestTask(task_id="a", source_type="text", error="e1"), "")
        dlq.archive(IngestTask(task_id="b", source_type="pdf", error="e2"), "")
        tasks = dlq.list_archived()
        assert len(tasks) == 2
        assert sorted(t["task_id"] for t in tasks) == ["a", "b"]
    finally:
        shutil.rmtree(tmpdir)
