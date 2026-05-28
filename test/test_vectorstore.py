"""单元测试 - MilvusVectorStore"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "kgsrc"))

from langchain_core.documents import Document
from knowledge_vector.vectorstore import get_embeddings, MilvusVectorStore


class TestGetEmbeddings:
    """get_embeddings 单元测试"""

    def test_get_embeddings_returns_huggingface_embeddings(self):
        """测试返回 HuggingFaceEmbeddings 实例"""
        with patch("knowledge_vector.vectorstore.HuggingFaceEmbeddings"):
            embeddings = get_embeddings()
            # 返回的是 mock 对象，因为在测试环境中不会真正加载模型

    def test_get_embeddings_with_custom_model(self):
        """测试使用自定义模型"""
        with patch("knowledge_vector.vectorstore.HuggingFaceEmbeddings") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance

            embeddings = get_embeddings(model="custom/model")
            mock_cls.assert_called_once()


class TestMilvusVectorStore:
    """MilvusVectorStore 单元测试"""

    @patch("knowledge_vector.vectorstore.MilvusClient")
    def test_init(self, mock_client_cls):
        """测试初始化"""
        store = MilvusVectorStore(collection_name="test_collection")
        assert store.collection_name == "test_collection"

    @patch("knowledge_vector.vectorstore.MilvusClient")
    def test_get_client(self, mock_client_cls):
        """测试获取客户端"""
        mock_instance = MagicMock()
        mock_client_cls.return_value = mock_instance

        store = MilvusVectorStore()
        client = store._get_client()

        mock_client_cls.assert_called_once()

    @patch("knowledge_vector.vectorstore.MilvusClient")
    @patch("knowledge_vector.vectorstore.get_embeddings")
    def test_create_from_documents(self, mock_get_emb, mock_client_cls):
        """测试从文档创建向量存储"""
        # Mock embeddings
        mock_emb = MagicMock()
        mock_emb.embed_query.return_value = [0.1] * 10
        mock_emb.embed_documents.return_value = [[0.1] * 10, [0.2] * 10]
        mock_get_emb.return_value = mock_emb

        # Mock client
        mock_client = MagicMock()
        mock_client.list_collections.return_value = []
        mock_client_cls.return_value = mock_client

        store = MilvusVectorStore()

        docs = [
            Document(page_content="Content 1", metadata={"source": "doc1.md"}),
            Document(page_content="Content 2", metadata={"source": "doc2.md"}),
        ]

        result = store.create_from_documents(docs)

        assert result is store
        mock_client.create_collection.assert_called_once()
        mock_client.insert.assert_called_once()

    @patch("knowledge_vector.vectorstore.MilvusClient")
    @patch("knowledge_vector.vectorstore.get_embeddings")
    def test_create_from_documents_drop_old(self, mock_get_emb, mock_client_cls):
        """测试删除旧集合再创建"""
        mock_emb = MagicMock()
        mock_emb.embed_query.return_value = [0.1] * 10
        mock_emb.embed_documents.return_value = [[0.1] * 10]
        mock_get_emb.return_value = mock_emb

        mock_client = MagicMock()
        mock_client.list_collections.return_value = ["test_collection"]
        mock_client_cls.return_value = mock_client

        store = MilvusVectorStore(collection_name="test_collection")

        docs = [Document(page_content="Content", metadata={"source": "doc.md"})]

        store.create_from_documents(docs, drop_old=True)

        mock_client.drop_collection.assert_called_once_with("test_collection")

    @patch("knowledge_vector.vectorstore.MilvusClient")
    @patch("knowledge_vector.vectorstore.get_embeddings")
    def test_search(self, mock_get_emb, mock_client_cls):
        """测试搜索返回正确格式的文档"""
        mock_emb = MagicMock()
        mock_emb.embed_query.return_value = [0.1] * 10
        mock_get_emb.return_value = mock_emb

        mock_client = MagicMock()
        mock_client.search.return_value = [[
            {"entity": {"text": "Test content", "source": "test.md"}},
            {"entity": {"text": "Test content 2", "source": "test2.md"}},
        ]]
        mock_client_cls.return_value = mock_client

        store = MilvusVectorStore()

        results = store.search("test query", k=2)

        assert len(results) == 2
        assert isinstance(results[0], Document)
        assert results[0].page_content == "Test content"
        assert results[0].metadata["source"] == "test.md"

    @patch("knowledge_vector.vectorstore.MilvusClient")
    @patch("knowledge_vector.vectorstore.get_embeddings")
    def test_similarity_search_with_score(self, mock_get_emb, mock_client_cls):
        """测试带分数的相似度搜索"""
        mock_emb = MagicMock()
        mock_emb.embed_query.return_value = [0.1] * 10
        mock_get_emb.return_value = mock_emb

        mock_client = MagicMock()
        mock_client.search.return_value = [[
            {"entity": {"text": "Test content", "source": "test.md"}, "distance": 0.95},
        ]]
        mock_client_cls.return_value = mock_client

        store = MilvusVectorStore()

        results = store.similarity_search_with_score("test query", k=1)

        assert len(results) == 1
        doc, score = results[0]
        assert isinstance(doc, Document)
        assert score == 0.95

    @patch("knowledge_vector.vectorstore.MilvusClient")
    def test_load(self, mock_client_cls):
        """测试加载方法"""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        store = MilvusVectorStore()
        result = store.load()

        assert result is store

    @patch("knowledge_vector.vectorstore.MilvusClient")
    def test_client_property(self, mock_client_cls):
        """测试 client 属性"""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        store = MilvusVectorStore()
        client = store.client

        assert client is mock_client


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
