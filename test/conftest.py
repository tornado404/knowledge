"""Pytest 共享 fixtures 和配置"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.documents import Document

# 添加 kgsrc 到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent / "kgsrc"))


@pytest.fixture
def sample_documents():
    """Sample Document objects for testing"""
    return [
        Document(page_content="This is the first document content about AI.", metadata={"source": "doc1.md"}),
        Document(page_content="This is the second document content about ML.", metadata={"source": "doc2.md"}),
        Document(page_content="This is the third document content about Python.", metadata={"source": "doc3.md"}),
    ]


@pytest.fixture
def mock_agent_state():
    """Sample AgentState for node testing"""
    return {
        "messages": [{"role": "user", "content": "test question"}],
        "question": "What is AI?",
        "context": "",
        "web_context": "",
        "answer": "",
        "route_decision": "vector_only",
        "sources": [],
        "web_search_done": False,
    }


@pytest.fixture
def mock_agent_state_both():
    """Sample AgentState for 'both' route testing"""
    return {
        "messages": [{"role": "user", "content": "test question"}],
        "question": "What is the latest news about AI?",
        "context": "[文档1] (doc1.md)\nAI is artificial intelligence.",
        "web_context": "",
        "answer": "",
        "route_decision": "both",
        "sources": [{"type": "vector", "source": "doc1.md", "content": "AI is artificial intelligence."}],
        "web_search_done": False,
    }


@pytest.fixture
def mock_agent_state_web_only():
    """Sample AgentState for 'web_only' route testing"""
    return {
        "messages": [{"role": "user", "content": "test question"}],
        "question": "What's the weather today?",
        "context": "",
        "web_context": "",
        "answer": "",
        "route_decision": "web_only",
        "sources": [],
        "web_search_done": False,
    }


@pytest.fixture
def mock_vectorstore():
    """Mock MilvusVectorStore"""
    mock = MagicMock()
    mock.search.return_value = [
        Document(page_content="Mock content", metadata={"source": "mock.md"})
    ]
    return mock


@pytest.fixture
def mock_llm_response():
    """Mock LLM response"""
    mock = MagicMock()
    mock.content = "This is a mock LLM response."
    return mock


@pytest.fixture
def mock_llm_response_list():
    """Mock LLM response with list content"""
    mock = MagicMock()
    mock.content = [{"type": "text", "text": "vector_only"}]
    return mock


@pytest.fixture
def mock_tavily_response():
    """Mock Tavily search response"""
    return {
        "results": [
            {
                "title": "Test Article",
                "url": "https://example.com/article",
                "content": "This is the content of the test article."
            }
        ],
        "answer": "Test answer summary"
    }
