"""向量库搜索测试"""

import sys
import os
import logging
from pathlib import Path

import pytest

# Suppress warnings before any imports
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("huggingface").setLevel(logging.ERROR)

sys.path.insert(0, str(Path(__file__).parent.parent / "kgsrc"))

from knowledge_vector.vectorstore import MilvusVectorStore


@pytest.mark.skipif(
    not os.environ.get("TEST_MILVUS"),
    reason="Milvus not available, set TEST_MILVUS=1 to run"
)
class TestMilvusSearch:
    """Milvus 向量库搜索测试"""

    def test_search_returns_results(self):
        """测试搜索返回结果"""
        vs = MilvusVectorStore()
        vs.load()

        results = vs.search("test query", k=4)

        assert isinstance(results, list)

    def test_search_with_k(self):
        """测试指定 k 参数"""
        vs = MilvusVectorStore()
        vs.load()

        results = vs.search("test query", k=2)

        assert len(results) <= 2

    def test_search_documents_have_metadata(self):
        """测试返回的文档包含 metadata"""
        vs = MilvusVectorStore()
        vs.load()

        results = vs.search("test query", k=1)

        if results:
            assert "source" in results[0].metadata
