"""Milvus 向量检索工具"""
from typing import Optional, List

from .base import BaseTool, ToolResult
from knowledge_vector.config import config


class MilvusSearchTool(BaseTool):
    """Milvus 向量库检索工具"""

    def __init__(
        self,
        collection_name: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
    ):
        super().__init__(
            name="milvus_search",
            description="Search knowledge base using Milvus vector store"
        )
        self.collection_name = collection_name or config.milvus_collection
        self.host = host or config.milvus_host
        self.port = port or config.milvus_port

    async def execute(
        self,
        query: str,
        top_k: int = 5,
        **kwargs
    ) -> ToolResult:
        """执行向量检索"""
        try:
            from pymilvus import MilvusClient

            client = MilvusClient(
                uri=f"http://{self.host}:{self.port}"
            )

            # 检查 collection 是否存在
            if not client.has_collection(self.collection_name):
                return ToolResult(
                    success=False,
                    error=f"Collection '{self.collection_name}' not found"
                )

            # 搜索
            results = client.search(
                collection_name=self.collection_name,
                data=[query],
                limit=top_k,
                output_fields=["text", "source"]
            )

            if not results or not results[0]:
                return ToolResult(
                    success=True,
                    output="No results found",
                    metadata={"hit_count": 0}
                )

            # 格式化结果
            output_lines = []
            for i, hit in enumerate(results[0], 1):
                text = hit.get("entity", {}).get("text", "")
                source = hit.get("entity", {}).get("source", "unknown")
                score = hit.get("distance", 0)
                output_lines.append(
                    f"[{i}] Score: {score:.4f}\n"
                    f"    Source: {source}\n"
                    f"    Content: {text[:300]}..."
                )

            return ToolResult(
                success=True,
                output="\n\n".join(output_lines),
                metadata={
                    "query": query,
                    "hit_count": len(results[0])
                }
            )
        except ImportError:
            return ToolResult(
                success=False,
                error="pymilvus not installed"
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e)
            )

    async def get_context(self, query: str, top_k: int = 3) -> str:
        """获取检索上下文（用于 RAG）"""
        try:
            from pymilvus import MilvusClient

            client = MilvusClient(uri=f"http://{self.host}:{self.port}")

            if not client.has_collection(self.collection_name):
                return ""

            results = client.search(
                collection_name=self.collection_name,
                data=[query],
                limit=top_k,
                output_fields=["text"]
            )

            if not results or not results[0]:
                return ""

            context_parts = []
            for hit in results[0]:
                text = hit.get("entity", {}).get("text", "")
                if text:
                    context_parts.append(text)

            return "\n\n".join(context_parts)
        except Exception:
            return ""
