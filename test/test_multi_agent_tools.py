"""测试 Multi-Agent 工具集"""
import pytest
import asyncio
from kgsrc.knowledge_vector.multi_agent.tools import (
    BaseTool, ToolResult,
    BashTool, LsTool, CatTool, GrepTool, FindTool,
    WebSearchTool, MilvusSearchTool
)


class TestToolResult:
    """测试 ToolResult 数据类"""

    def test_tool_result_creation(self):
        result = ToolResult(success=True, output="test output")
        assert result.success is True
        assert result.output == "test output"
        assert result.error is None

    def test_tool_result_failure(self):
        result = ToolResult(success=False, error="test error")
        assert result.success is False
        assert result.error == "test error"

    def test_tool_result_to_dict(self):
        result = ToolResult(success=True, output="test")
        d = result.to_dict()
        assert d["success"] is True
        assert d["output"] == "test"


class TestBashTool:
    """测试 BashTool"""

    @pytest.mark.asyncio
    async def test_bash_pwd(self):
        tool = BashTool(timeout=10)
        result = await tool.execute("pwd")
        assert result.success is True
        assert len(result.output) > 0

    @pytest.mark.asyncio
    async def test_bash_blocked_command(self):
        tool = BashTool()
        result = await tool.execute("rm -rf /")
        assert result.success is False
        assert "not allowed" in result.error.lower() or "blocked" in result.error.lower()

    @pytest.mark.asyncio
    async def test_bash_invalid_command(self):
        tool = BashTool(allowed_commands=["ls"])
        result = await tool.execute("unknown_command arg")
        assert result.success is False


class TestLsTool:
    """测试 LsTool"""

    @pytest.mark.asyncio
    async def test_ls_current_dir(self):
        tool = LsTool(base_path="/tmp")
        result = await tool.execute(path=".")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_ls_nonexistent_path(self):
        tool = LsTool(base_path="/tmp")
        result = await tool.execute(path="nonexistent_path_12345")
        assert result.success is False


class TestGrepTool:
    """测试 GrepTool"""

    @pytest.mark.asyncio
    async def test_grep_file_not_found(self):
        tool = GrepTool(base_path="/tmp")
        result = await tool.execute(
            pattern="test",
            path="nonexistent_file_12345",
            recursive=False
        )
        assert result.success is False


class TestFindTool:
    """测试 FindTool"""

    @pytest.mark.asyncio
    async def test_find_nonexistent_path(self):
        tool = FindTool(base_path="/tmp")
        result = await tool.execute(
            name_pattern="*.txt",
            path="nonexistent_path_12345"
        )
        assert result.success is False

    @pytest.mark.asyncio
    async def test_find_no_matches(self):
        tool = FindTool(base_path="/tmp")
        result = await tool.execute(
            name_pattern="nonexistent_file_12345_*.xyz"
        )
        assert result.success is True
        assert "No matches" in result.output


class TestWebSearchTool:
    """测试 WebSearchTool"""

    @pytest.mark.asyncio
    async def test_websearch_no_api_key(self):
        tool = WebSearchTool(api_key="")
        result = await tool.execute(query="test")
        assert result.success is False
        assert "not configured" in result.error.lower()


class TestMilvusSearchTool:
    """测试 MilvusSearchTool"""

    @pytest.mark.asyncio
    async def test_milvus_no_connection(self):
        tool = MilvusSearchTool(
            collection_name="nonexistent_collection",
            host="localhost",
            port=19530
        )
        result = await tool.execute(query="test")
        # Milvus 连接失败或 collection 不存在
        assert result.success is False or "not found" in result.output.lower()
