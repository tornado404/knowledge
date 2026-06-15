import tempfile
import shutil
from unittest.mock import patch, MagicMock
from kgsrc.pkos.pipeline import IngestPipeline
from kgsrc.pkos.models import TaskStatus


def test_e2e_text_ingest():
    tmpdir = tempfile.mkdtemp()
    try:
        pipeline = IngestPipeline(
            task_dir=f"{tmpdir}/tasks",
            vault_dir=f"{tmpdir}/vault",
            dlq_dir=f"{tmpdir}/dlq",
        )

        # Mock classifier
        mock_cls = MagicMock()
        mock_cls.title = "测试文档"
        mock_cls.summary = "这是一个测试"
        mock_cls.topic = "测试"
        mock_cls.identities = ["开发者"]
        mock_cls.tags = ["test", "pkos"]

        with patch.object(pipeline.classifier, "classify_content", return_value=mock_cls):
            with patch.object(pipeline.indexer, "index_document", return_value=True):
                task = pipeline.register(source_type="text", source_url="https://example.com")
                success = pipeline.process_task(
                    task.task_id,
                    raw_text="# 测试文档\n\n这是正文内容。",
                )

        assert success is True
        final = pipeline.store.load(task.task_id)
        assert final.status == TaskStatus.INDEXED
        assert final.vault_path is not None
        assert "测试" in final.vault_path
    finally:
        shutil.rmtree(tmpdir)


def test_e2e_web_ingest():
    tmpdir = tempfile.mkdtemp()
    try:
        pipeline = IngestPipeline(
            task_dir=f"{tmpdir}/tasks",
            vault_dir=f"{tmpdir}/vault",
            dlq_dir=f"{tmpdir}/dlq",
        )

        mock_cls = MagicMock()
        mock_cls.title = "网页测试"
        mock_cls.summary = "网页摘要"
        mock_cls.topic = "未分类"
        mock_cls.identities = []
        mock_cls.tags = ["web"]

        html = "<html><head><title>Page Title</title></head><body><h1>Heading</h1><p>Content</p></body></html>"

        with patch.object(pipeline.classifier, "classify_content", return_value=mock_cls):
            with patch.object(pipeline.indexer, "index_document", return_value=True):
                task = pipeline.register(source_type="web")
                success = pipeline.process_task(task.task_id, raw_text=html)

        assert success is True
        final = pipeline.store.load(task.task_id)
        assert final.status == TaskStatus.INDEXED
    finally:
        shutil.rmtree(tmpdir)
