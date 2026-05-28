"""单元测试 - RAGChain"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "kgsrc"))

from langchain_core.documents import Document
from knowledge_vector.chain import RAGChain, create_rag_chain


class TestRAGChain:
    """RAGChain 单元测试"""

    @patch("knowledge_vector.chain.MilvusVectorStore")
    @patch("knowledge_vector.chain.ChatAnthropic")
    def test_create_rag_chain(self, mock_llm, mock_vectorstore_cls):
        """测试创建 RAG Chain"""
        mock_vectorstore_cls.return_value = MagicMock()
        mock_llm.return_value = MagicMock()

        chain = create_rag_chain(use_history=True)
        assert isinstance(chain, RAGChain)
        assert chain.use_history is True

    @patch("knowledge_vector.chain.MilvusVectorStore")
    @patch("knowledge_vector.chain.ChatAnthropic")
    def test_build_context(self, mock_llm, mock_vectorstore_cls, sample_documents):
        """测试 context 构建格式"""
        mock_vs = MagicMock()
        mock_vs.load.return_value = None
        mock_vectorstore_cls.return_value = mock_vs
        mock_llm.return_value = MagicMock()

        chain = RAGChain()
        chain.vectorstore.search.return_value = sample_documents

        context = chain._build_context(sample_documents)

        assert "[文档1]" in context
        assert "doc1.md" in context
        assert "This is the first document" in context
        assert "[文档2]" in context
        assert "doc2.md" in context

    @patch("knowledge_vector.chain.MilvusVectorStore")
    @patch("knowledge_vector.chain.ChatAnthropic")
    def test_build_context_empty(self, mock_llm, mock_vectorstore_cls):
        """测试空文档构建 context"""
        mock_vs = MagicMock()
        mock_vectorstore_cls.return_value = mock_vs
        mock_llm.return_value = MagicMock()

        chain = RAGChain()
        context = chain._build_context([])
        assert context == ""

    @patch("knowledge_vector.chain.MilvusVectorStore")
    @patch("knowledge_vector.chain.ChatAnthropic")
    def test_invoke_without_history(self, mock_llm_cls, mock_vectorstore_cls, sample_documents):
        """测试单轮问答（无历史）"""
        mock_vs = MagicMock()
        mock_vs.load.return_value = None
        mock_vs.search.return_value = sample_documents
        mock_vectorstore_cls.return_value = mock_vs

        chain = RAGChain(use_history=False)
        # Mock chain.invoke 直接返回结果
        with patch.object(chain, "chain") as mock_chain:
            mock_chain.invoke.return_value = "This is the answer."
            answer = chain.invoke(question="What is AI?")
            assert isinstance(answer, str)
            mock_vs.search.assert_called_once()

    @patch("knowledge_vector.chain.MilvusVectorStore")
    @patch("knowledge_vector.chain.ChatAnthropic")
    def test_invoke_with_history(self, mock_llm_cls, mock_vectorstore_cls, sample_documents):
        """测试多轮问答（有历史）"""
        mock_vs = MagicMock()
        mock_vs.load.return_value = None
        mock_vs.search.return_value = sample_documents
        mock_vectorstore_cls.return_value = mock_vs

        chain = RAGChain(use_history=True)
        with patch.object(chain, "chain") as mock_chain:
            mock_chain.invoke.return_value = "This is the answer with history."
            history = "用户: Hello\n助手: Hi there!"
            answer = chain.invoke(question="What is AI?", history=history)
            assert isinstance(answer, str)
            mock_vs.search.assert_called_once()

    @patch("knowledge_vector.chain.MilvusVectorStore")
    @patch("knowledge_vector.chain.ChatAnthropic")
    def test_retrieve(self, mock_llm_cls, mock_vectorstore_cls, sample_documents):
        """测试仅检索不生成"""
        mock_vs = MagicMock()
        mock_vs.load.return_value = None
        mock_vs.search.return_value = sample_documents
        mock_vectorstore_cls.return_value = mock_vs

        chain = RAGChain()
        docs = chain.retrieve(query="What is AI?", k=3)

        assert len(docs) == 3
        mock_vs.search.assert_called_once_with("What is AI?", k=3)

    @patch("knowledge_vector.chain.MilvusVectorStore")
    @patch("knowledge_vector.chain.ChatAnthropic")
    def test_invoke_with_filter(self, mock_llm_cls, mock_vectorstore_cls, sample_documents):
        """测试带 filter 的检索"""
        mock_vs = MagicMock()
        mock_vs.load.return_value = None
        mock_vs.search.return_value = sample_documents[:1]
        mock_vectorstore_cls.return_value = mock_vs

        chain = RAGChain()
        with patch.object(chain, "chain") as mock_chain:
            mock_chain.invoke.return_value = "Answer"
            chain.invoke(question="test", filter="source == 'doc1.md'")
            mock_vs.search.assert_called_once()
            call_args = mock_vs.search.call_args
            assert call_args[1]["filter"] == "source == 'doc1.md'"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
