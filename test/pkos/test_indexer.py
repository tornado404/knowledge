import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
from kgsrc.pkos.indexer import VaultIndexer


def test_indexer_index_document_mock():
    indexed_file = tempfile.mktemp(suffix=".json")
    indexer = VaultIndexer(vault_dir="/tmp", indexed_file=indexed_file)

    mock_vs = MagicMock()
    mock_vs.create_from_documents.return_value = mock_vs

    mock_doc = MagicMock()

    try:
        with patch.object(indexer, "_get_vectorstore", return_value=mock_vs), \
             patch("kgsrc.pkos.indexer.Path.exists", return_value=True), \
             patch("kgsrc.pkos.indexer.MarkdownLoader.load_single", return_value=[mock_doc]), \
             patch("kgsrc.pkos.indexer.split_documents", return_value=[mock_doc]):
            result = indexer.index_document("/tmp/fake.md")
            assert result is True
    finally:
        if Path(indexed_file).exists():
            Path(indexed_file).unlink()


def test_indexer_get_indexed():
    tmpdir = tempfile.mkdtemp()
    indexed_file = tempfile.mktemp(suffix=".json")
    try:
        indexer = VaultIndexer(vault_dir=tmpdir, indexed_file=indexed_file)
        # Initially empty
        indexed = indexer.get_indexed_documents()
        assert indexed == []
    finally:
        shutil.rmtree(tmpdir)
        if Path(indexed_file).exists():
            Path(indexed_file).unlink()


def test_indexer_mark_indexed():
    tmpdir = tempfile.mkdtemp()
    indexed_file = tempfile.mktemp(suffix=".json")
    try:
        indexer = VaultIndexer(vault_dir=tmpdir, indexed_file=indexed_file)
        indexer.mark_indexed("/tmp/doc1.md")
        indexed = indexer.get_indexed_documents()
        assert "/tmp/doc1.md" in indexed
    finally:
        shutil.rmtree(tmpdir)
        if Path(indexed_file).exists():
            Path(indexed_file).unlink()
