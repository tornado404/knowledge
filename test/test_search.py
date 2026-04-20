"""向量库搜索测试"""

import sys
import os
import logging
from pathlib import Path

# Suppress warnings before any imports
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"  # Suppress TensorFlow warnings
logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("huggingface").setLevel(logging.ERROR)

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from knowledge_vector import MilvusVectorStore


def test_search(query: str, k: int = 4):
    """测试搜索功能"""
    print(f"\n{'='*60}")
    print(f"查询: {query}")
    print(f"{'='*60}")

    vs = MilvusVectorStore()
    vs.load()

    results = vs.search(query, k=k)

    print(f"\n找到 {len(results)} 个结果:\n")
    for i, doc in enumerate(results, 1):
        source = doc.metadata.get("source", "unknown")
        content = doc.page_content[:200].replace("\n", " ")
        print(f"{i}. [{source}]")
        print(f"   {content}...")
        print()

    return results


def main():
    # 测试查询
    queries = [
        "claude code的Tools如何编写和调用",
        "LangChain如何搭建带有知识库的对话bot",
    ]

    for query in queries:
        test_search(query)


if __name__ == "__main__":
    main()
