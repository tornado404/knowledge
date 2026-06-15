import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
from kgsrc.pkos.pipeline import IngestPipeline
from kgsrc.pkos.models import TaskStatus


def test_pipeline_register():
    tmpdir = tempfile.mkdtemp()
    try:
        pipeline = IngestPipeline(
            task_dir=tmpdir,
            vault_dir=f"{tmpdir}/vault",
            dlq_dir=f"{tmpdir}/dlq",
        )
        task = pipeline.register(source_type="text", source_url="https://example.com")
        assert task.status == TaskStatus.REGISTERED
        assert task.task_id is not None

        loaded = pipeline.store.load(task.task_id)
        assert loaded is not None
        assert loaded.source_type == "text"
    finally:
        shutil.rmtree(tmpdir)


def test_pipeline_process_text_mock():
    tmpdir = tempfile.mkdtemp()
    try:
        pipeline = IngestPipeline(
            task_dir=tmpdir,
            vault_dir=f"{tmpdir}/vault",
            dlq_dir=f"{tmpdir}/dlq",
        )
        task = pipeline.register(source_type="text")
        task_id = task.task_id

        # Mock classifier to avoid LLM call
        mock_result = MagicMock()
        mock_result.title = "Test Title"
        mock_result.summary = "Test Summary"
        mock_result.topic = "测试"
        mock_result.identities = ["程序员"]
        mock_result.tags = ["test"]

        with patch.object(pipeline.classifier, "classify_content", return_value=mock_result):
            with patch.object(pipeline.indexer, "index_document", return_value=True):
                result = pipeline.process_task(task_id, raw_text="Hello world content here")

        assert result is True
        updated = pipeline.store.load(task_id)
        assert updated.status == TaskStatus.INDEXED
        assert updated.vault_path is not None
    finally:
        shutil.rmtree(tmpdir)


def test_pipeline_retry_limit():
    tmpdir = tempfile.mkdtemp()
    try:
        pipeline = IngestPipeline(
            task_dir=tmpdir,
            vault_dir=f"{tmpdir}/vault",
            dlq_dir=f"{tmpdir}/dlq",
        )
        task = pipeline.register(source_type="text")
        task_id = task.task_id

        # Force failure in classify stage
        with patch("time.sleep"):
            with patch.object(pipeline.classifier, "classify_content", side_effect=Exception("fail")):
                result = pipeline.process_task(task_id, raw_text="text")

        assert result is True
        updated = pipeline.store.load(task_id)
        assert updated.status == TaskStatus.INDEXED
        assert updated.retry_count == 3
    finally:
        shutil.rmtree(tmpdir)


def test_pipeline_get_status():
    tmpdir = tempfile.mkdtemp()
    try:
        pipeline = IngestPipeline(
            task_dir=tmpdir,
            vault_dir=f"{tmpdir}/vault",
            dlq_dir=f"{tmpdir}/dlq",
        )
        task = pipeline.register(source_type="text")
        status = pipeline.get_status(task.task_id)
        assert status == TaskStatus.REGISTERED
    finally:
        shutil.rmtree(tmpdir)
