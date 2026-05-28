"""单元测试 - LangGraph Agent"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "kgsrc"))

from langchain_core.documents import Document
from knowledge_vector.agent import (
    AgentState,
    route_node,
    retrieve_node,
    web_search_node,
    merge_context_node,
    generate_node,
    route_to_retrieval,
    after_retrieval_or_websearch,
    create_rag_agent_graph,
    create_rag_agent,
    regex_route,
    llm_route,
    post_route,
    REGEX_ROUTES,
)


class TestRouteNode:
    """route_node 单元测试"""

    @patch("knowledge_vector.agent.ChatAnthropic")
    def test_route_node_vector_only(self, mock_llm_cls, mock_agent_state):
        """测试 route_node 返回 vector_only"""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "vector_only"
        mock_llm.invoke.return_value = mock_response
        mock_llm_cls.return_value = mock_llm

        result = route_node(mock_agent_state)

        assert "route_decision" in result
        assert result["route_decision"] == "vector_only"

    @patch("knowledge_vector.agent.ChatAnthropic")
    def test_route_node_web_only(self, mock_llm_cls, mock_agent_state):
        """测试 route_node 返回 web_only"""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "web_only"
        mock_llm.invoke.return_value = mock_response
        mock_llm_cls.return_value = mock_llm

        result = route_node(mock_agent_state)

        assert result["route_decision"] == "web_only"

    @patch("knowledge_vector.agent.ChatAnthropic")
    def test_route_node_both(self, mock_llm_cls, mock_agent_state):
        """测试 route_node 返回 both"""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "both"
        mock_llm.invoke.return_value = mock_response
        mock_llm_cls.return_value = mock_llm

        result = route_node(mock_agent_state)

        assert result["route_decision"] == "both"

    @patch("knowledge_vector.agent.ChatAnthropic")
    def test_route_node_invalid_response_defaults_to_vector_only(self, mock_llm_cls, mock_agent_state):
        """测试 route_node 无效响应默认为 vector_only"""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "invalid_response"
        mock_llm.invoke.return_value = mock_response
        mock_llm_cls.return_value = mock_llm

        result = route_node(mock_agent_state)

        assert result["route_decision"] == "vector_only"

    @patch("knowledge_vector.agent.ChatAnthropic")
    def test_route_node_handles_list_content(self, mock_llm_cls, mock_agent_state):
        """测试 route_node 处理 list 格式的响应"""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [{"type": "text", "text": "vector_only"}]
        mock_llm.invoke.return_value = mock_response
        mock_llm_cls.return_value = mock_llm

        result = route_node(mock_agent_state)

        assert result["route_decision"] == "vector_only"

    @patch("knowledge_vector.agent.ChatAnthropic")
    def test_route_node_handles_dict_content(self, mock_llm_cls, mock_agent_state):
        """测试 route_node 处理 dict 格式的响应"""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = {"type": "text", "text": "web_only"}
        mock_llm.invoke.return_value = mock_response
        mock_llm_cls.return_value = mock_llm

        result = route_node(mock_agent_state)

        assert result["route_decision"] == "web_only"

    @patch("knowledge_vector.agent.ChatAnthropic")
    def test_route_node_empty_response_uses_fallback(self, mock_llm_cls, mock_agent_state):
        """测试 route_node LLM 返回空时使用降级策略"""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = ""  # 空响应
        mock_llm.invoke.return_value = mock_response
        mock_llm_cls.return_value = mock_llm

        result = route_node(mock_agent_state)

        # 应该使用默认值 vector_only
        assert result["route_decision"] == "vector_only"

    @patch("knowledge_vector.agent.ChatAnthropic")
    def test_route_node_empty_response_with_regex_fallback(self, mock_llm_cls, mock_agent_state):
        """测试 route_node LLM 返回空但正则有结果时使用正则结果"""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = ""  # 空响应
        mock_llm.invoke.return_value = mock_response
        mock_llm_cls.return_value = mock_llm

        state = {**mock_agent_state, "question": "今天天气怎么样"}
        result = route_node(state)

        # 应该使用正则结果 web_only
        assert result["route_decision"] == "web_only"

    @patch("knowledge_vector.agent.ChatAnthropic")
    def test_route_node_exception_uses_fallback(self, mock_llm_cls, mock_agent_state):
        """测试 route_node LLM 异常时使用降级策略"""
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = Exception("API Error")
        mock_llm_cls.return_value = mock_llm

        result = route_node(mock_agent_state)

        # 应该使用默认值 vector_only
        assert result["route_decision"] == "vector_only"


class TestRegexRoute:
    """regex_route 单元测试"""

    def test_regex_route_web_only_weather(self):
        """测试正则命中天气关键词"""
        assert regex_route("今天天气怎么样") == "web_only"
        assert regex_route("明天温度多少") == "web_only"
        assert regex_route("北京气温如何") == "web_only"

    def test_regex_route_web_only_time(self):
        """测试正则命中时间关键词"""
        assert regex_route("今天的新闻") == "web_only"
        assert regex_route("明天的比赛") == "web_only"
        assert regex_route("今年的股价") == "web_only"

    def test_regex_route_both(self):
        """测试正则命中 both 关键词"""
        assert regex_route("miniMind和ChatGPT的区别") == "both"
        assert regex_route("对比一下这两个项目") == "both"
        assert regex_route("有什么差异") == "both"

    def test_regex_route_vector_only(self):
        """测试正则命中 vector_only 关键词"""
        # RAG的原理 - 包含 "原理"
        assert regex_route("RAG的原理是什么") == "vector_only"
        # 项目架构设计 - 包含 "架构"
        assert regex_route("项目的架构设计") == "vector_only"
        # 如何实现 - 包含 "如何实现"
        assert regex_route("如何实现这个算法") == "vector_only"

    def test_regex_route_no_match(self):
        """测试正则未命中时返回 None"""
        assert regex_route("miniMind项目") is None
        # "帮我写代码" 命中 "代码" -> vector_only
        assert regex_route("miniMind项目介绍") is None


class TestLLMRoute:
    """llm_route 单元测试"""

    @patch("knowledge_vector.agent.ChatAnthropic")
    def test_llm_route_returns_decision(self, mock_llm_cls):
        """测试 llm_route 返回有效决策"""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "vector_only"
        mock_llm.invoke.return_value = mock_response
        mock_llm_cls.return_value = mock_llm

        result = llm_route("什么是RAG")

        assert result == "vector_only"
        mock_llm.invoke.assert_called_once()

    @patch("knowledge_vector.agent.ChatAnthropic")
    def test_llm_route_with_pre_decision(self, mock_llm_cls):
        """测试 llm_route 传入正则预处理结果"""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "web_only"
        mock_llm.invoke.return_value = mock_response
        mock_llm_cls.return_value = mock_llm

        result = llm_route("今天天气", pre_decision="web_only")

        assert result == "web_only"

    @patch("knowledge_vector.agent.ChatAnthropic")
    def test_llm_route_exception_uses_pre(self, mock_llm_cls):
        """测试 llm_route 异常时使用 pre_decision"""
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = Exception("API Error")
        mock_llm_cls.return_value = mock_llm

        result = llm_route("test", pre_decision="both")

        assert result == "both"

    @patch("knowledge_vector.agent.ChatAnthropic")
    def test_llm_route_exception_no_pre(self, mock_llm_cls):
        """测试 llm_route 异常且无 pre_decision 时使用默认值"""
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = Exception("API Error")
        mock_llm_cls.return_value = mock_llm

        result = llm_route("test")

        assert result == "vector_only"


class TestPostRoute:
    """post_route 单元测试"""

    def test_post_route_returns_llm(self):
        """测试 post_route 返回 LLM 结果"""
        result = post_route("test", pre="web_only", llm="vector_only")
        assert result == "vector_only"

    def test_post_route_logs_decision(self):
        """测试 post_route 正确记录日志"""
        import io
        import sys

        old_stdout = sys.stdout
        sys.stdout = io.StringIO()

        post_route("test question", pre="both", llm="web_only")

        output = sys.stdout.getvalue()
        sys.stdout = old_stdout

        assert "决策依据" in output
        assert "正则=both" in output
        assert "LLM=web_only" in output


class TestRetrieveNode:
    """retrieve_node 单元测试"""

    @patch("knowledge_vector.agent.create_vectorstore_retriever")
    def test_retrieve_node(self, mock_create_retriever):
        """测试 retrieve_node 返回正确的 context 和 sources"""
        mock_vs = MagicMock()
        mock_vs.search.return_value = [
            Document(page_content="Test content", metadata={"source": "test.md"})
        ]
        mock_create_retriever.return_value = mock_vs

        state = {
            "messages": [],
            "question": "What is test?",
            "context": "",
            "web_context": "",
            "answer": "",
            "route_decision": "vector_only",
            "sources": [],
            "web_search_done": False,
        }

        result = retrieve_node(state)

        assert result["context"] != ""
        assert "sources" in result
        assert len(result["sources"]) == 1
        assert result["sources"][0]["type"] == "vector"


class TestWebSearchNode:
    """web_search_node 单元测试 - 需要 tavily 包"""

    @pytest.fixture(autouse=True)
    def check_tavily(self):
        """检查 tavily 是否安装"""
        pytest.importorskip("tavily", reason="tavily package not installed")

    def test_web_search_node_no_api_key(self, mock_agent_state_web_only):
        """测试无 Tavily API Key 时返回提示信息"""
        with patch("knowledge_vector.agent.config") as mock_config:
            mock_config.tavily_api_key = ""
            result = web_search_node(mock_agent_state_web_only)
            assert "web_context" in result

    def test_web_search_node_with_mock(self, mock_agent_state_web_only, mock_tavily_response):
        """测试有 API Key 时的网页搜索"""
        with patch("knowledge_vector.agent.config") as mock_config, \
             patch("knowledge_vector.agent.TavilyClient") as mock_tavily_cls:
            mock_config.tavily_api_key = "fake_api_key"
            mock_client = MagicMock()
            mock_client.search.return_value = mock_tavily_response
            mock_tavily_cls.return_value = mock_client

            result = web_search_node(mock_agent_state_web_only)
            assert "web_context" in result
            mock_client.search.assert_called_once()

    def test_web_search_node_handles_exception(self, mock_agent_state_web_only):
        """测试网页搜索异常处理"""
        with patch("knowledge_vector.agent.config") as mock_config, \
             patch("knowledge_vector.agent.TavilyClient") as mock_tavily_cls:
            mock_config.tavily_api_key = "fake_api_key"
            mock_client = MagicMock()
            mock_client.search.side_effect = Exception("Network error")
            mock_tavily_cls.return_value = mock_client

            result = web_search_node(mock_agent_state_web_only)
            assert "web_context" in result


class TestMergeContextNode:
    """merge_context_node 单元测试"""

    def test_merge_context_vector_only(self, mock_agent_state):
        """测试 vector_only 路由仅使用 context"""
        state = {
            **mock_agent_state,
            "route_decision": "vector_only",
            "context": "Knowledge base content",
            "web_context": "Web content",
        }

        result = merge_context_node(state)

        assert result["context"] == "Knowledge base content"

    def test_merge_context_web_only(self, mock_agent_state):
        """测试 web_only 路由仅使用 web_context"""
        state = {
            **mock_agent_state,
            "route_decision": "web_only",
            "context": "Knowledge base content",
            "web_context": "Web content",
        }

        result = merge_context_node(state)

        assert result["context"] == "Web content"

    def test_merge_context_both(self, mock_agent_state):
        """测试 both 路由合并两者"""
        state = {
            **mock_agent_state,
            "route_decision": "both",
            "context": "Knowledge base content",
            "web_context": "Web content",
        }

        result = merge_context_node(state)

        assert "Knowledge base content" in result["context"]
        assert "Web content" in result["context"]
        assert "【知识库" in result["context"] or "Knowledge base" in result["context"]


class TestGenerateNode:
    """generate_node 单元测试"""

    @patch("knowledge_vector.agent.ChatAnthropic")
    def test_generate_node(self, mock_llm_cls, mock_agent_state):
        """测试 generate_node 返回带 answer 的 state"""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "This is the generated answer."
        mock_llm.invoke.return_value = mock_response
        mock_llm_cls.return_value = mock_llm

        state = {
            **mock_agent_state,
            "context": "Reference content",
        }

        result = generate_node(state)

        assert "answer" in result
        assert result["answer"] == "This is the generated answer."

    @patch("knowledge_vector.agent.ChatAnthropic")
    def test_generate_node_handles_list_content(self, mock_llm_cls, mock_agent_state):
        """测试 generate_node 处理 list 格式响应"""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [{"type": "text", "text": "Answer from list."}]
        mock_llm.invoke.return_value = mock_response
        mock_llm_cls.return_value = mock_llm

        state = {
            **mock_agent_state,
            "context": "Reference content",
        }

        result = generate_node(state)

        assert result["answer"] == "Answer from list."


class TestConditionalEdges:
    """条件边函数单元测试"""

    def test_route_to_retrieval_vector_only(self, mock_agent_state):
        """测试 vector_only 路由"""
        state = {**mock_agent_state, "route_decision": "vector_only"}
        result = route_to_retrieval(state)
        assert result == "vector_only"

    def test_route_to_retrieval_web_only(self, mock_agent_state):
        """测试 web_only 路由"""
        state = {**mock_agent_state, "route_decision": "web_only"}
        result = route_to_retrieval(state)
        assert result == "web_search"

    def test_route_to_retrieval_both(self, mock_agent_state):
        """测试 both 路由"""
        state = {**mock_agent_state, "route_decision": "both"}
        result = route_to_retrieval(state)
        assert result == "both"

    def test_route_to_retrieval_default(self, mock_agent_state):
        """测试无效路由默认降级"""
        state = {**mock_agent_state, "route_decision": "invalid"}
        result = route_to_retrieval(state)
        assert result == "vector_only"

    def test_after_retrieval_or_websearch_not_both(self, mock_agent_state):
        """测试非 both 路由直接到 merge"""
        state = {**mock_agent_state, "route_decision": "vector_only"}
        result = after_retrieval_or_websearch(state)
        assert result == "merge"

    def test_after_retrieval_or_websearch_both_first(self, mock_agent_state_both):
        """测试 both 路由第一次执行后去 web_search"""
        state = {**mock_agent_state_both, "web_search_done": False}
        result = after_retrieval_or_websearch(state)
        assert result == "web_search"

    def test_after_retrieval_or_websearch_both_second(self, mock_agent_state_both):
        """测试 both 路由第二次执行后去 merge"""
        state = {**mock_agent_state_both, "web_search_done": True}
        result = after_retrieval_or_websearch(state)
        assert result == "merge"


class TestCreateRAGAgentGraph:
    """create_rag_agent_graph 单元测试"""

    def test_create_rag_agent_graph_compiles(self):
        """测试 graph 能成功编译"""
        graph = create_rag_agent_graph()
        compiled = graph.compile()
        assert compiled is not None

    def test_graph_has_required_nodes(self):
        """测试图包含所有必需的节点"""
        graph = create_rag_agent_graph()
        nodes = list(graph.nodes.keys())

        assert "route" in nodes
        assert "retrieve" in nodes
        assert "web_search" in nodes
        assert "merge" in nodes
        assert "generate" in nodes


class TestInvokeAgent:
    """invoke_agent 单元测试"""

    @patch("knowledge_vector.agent.create_rag_agent")
    def test_invoke_agent_returns_string(self, mock_create_agent):
        """测试 invoke_agent 返回字符串"""
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = {
            "messages": [],
            "question": "test",
            "context": "",
            "web_context": "",
            "answer": "This is the answer.",
            "route_decision": "vector_only",
            "sources": [],
        }
        mock_create_agent.return_value = mock_agent

        from knowledge_vector.agent import invoke_agent

        result = invoke_agent("test question")

        assert isinstance(result, str)
        assert result == "This is the answer."


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
