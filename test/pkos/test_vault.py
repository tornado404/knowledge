import sys
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from kgsrc.pkos.vault import VaultManager


def test_vault_write_and_read():
    tmpdir = tempfile.mkdtemp()
    try:
        vault = VaultManager(vault_dir=tmpdir)
        doc = vault.write_document(
            topic="人工智能",
            title="RAG 优化",
            content="## 关键要点\n\n- 要点一\n- 要点二",
            source_type="text",
            summary="RAG 优化摘要",
            identities=["程序员"],
            tags=["rag", "llm"],
            source_url="https://example.com",
        )
        assert doc is not None
        assert doc.exists()
        assert "人工智能" in str(doc)

        # Read back
        data = vault.read_document(str(doc))
        assert data["frontmatter"]["title"] == "RAG 优化"
        assert data["frontmatter"]["topic"] == "人工智能"
        assert data["frontmatter"]["tags"] == ["rag", "llm"]
        assert "要点一" in data["content"]
    finally:
        shutil.rmtree(tmpdir)


def test_vault_slugify():
    vault = VaultManager(vault_dir="/tmp")
    assert vault._slugify("Hello World") == "Hello-World"
    assert vault._slugify("测试 文档") == "测试-文档"
    assert vault._slugify("A/B Testing") == "A-B-Testing"


def test_vault_list_topics():
    tmpdir = tempfile.mkdtemp()
    try:
        vault = VaultManager(vault_dir=tmpdir)
        vault.write_document(topic="AI", title="T1", content="c1", source_type="text")
        vault.write_document(topic="Dev", title="T2", content="c2", source_type="text")
        topics = vault.list_topics()
        assert sorted(topics) == ["AI", "Dev"]
    finally:
        shutil.rmtree(tmpdir)


def test_vault_list_documents():
    tmpdir = tempfile.mkdtemp()
    try:
        vault = VaultManager(vault_dir=tmpdir)
        vault.write_document(topic="AI", title="T1", content="c1", source_type="text")
        vault.write_document(topic="AI", title="T2", content="c2", source_type="text")
        docs = vault.list_documents(topic="AI")
        assert len(docs) == 2
    finally:
        shutil.rmtree(tmpdir)
