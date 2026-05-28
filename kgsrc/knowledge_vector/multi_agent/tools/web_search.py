"""网页搜索工具 (基于 Tavily)"""
from typing import Optional, List

from .base import BaseTool, ToolResult
from knowledge_vector.config import config


class WebSearchTool(BaseTool):
    """Tavily 网页搜索工具"""

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(
            name="websearch",
            description="Search the web using Tavily"
        )
        self.api_key = api_key or config.tavily_api_key

    async def execute(
        self,
        query: str,
        max_results: int = 5,
        **kwargs
    ) -> ToolResult:
        """执行网页搜索"""
        if not self.api_key:
            return ToolResult(
                success=False,
                error="Tavily API key not configured"
            )

        try:
            from tavily import TavilyClient

            client = TavilyClient(api_key=self.api_key)
            results = client.search(
                query=query,
                max_results=max_results
            )

            # 格式化结果
            output_lines = []
            for i, result in enumerate(results.get("results", []), 1):
                output_lines.append(
                    f"[{i}] {result.get('title', 'N/A')}\n"
                    f"    URL: {result.get('url', 'N/A')}\n"
                    f"    {result.get('content', 'N/A')[:200]}..."
                )

            return ToolResult(
                success=True,
                output="\n\n".join(output_lines),
                metadata={
                    "query": query,
                    "result_count": len(results.get("results", []))
                }
            )
        except ImportError:
            return ToolResult(
                success=False,
                error="tavily-python not installed"
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e)
            )

    async def get_context(
        self,
        query: str,
        max_results: int = 3
    ) -> str:
        """获取搜索上下文（用于 RAG）"""
        if not self.api_key:
            return ""

        try:
            from tavily import TavilyClient

            client = TavilyClient(api_key=self.api_key)
            results = client.search(query=query, max_results=max_results)

            context_parts = []
            for result in results.get("results", [])[:max_results]:
                context_parts.append(result.get("content", ""))

            return "\n\n".join(context_parts)
        except Exception:
            return ""
