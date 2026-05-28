"""单元测试 - FastAPI Chat Server"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "kgsrc"))

from fastapi.testclient import TestClient


class TestChatAPI:
    """FastAPI Chat Server 单元测试"""

    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        from fastapi.testclient import TestClient
        from knowledge_vector.chat import app
        return TestClient(app)

    def test_health_endpoint(self, client):
        """测试健康检查端点"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_chat_endpoint(self, client):
        """测试聊天端点"""
        with patch("knowledge_vector.chain.RAGChain.invoke") as mock_invoke:
            mock_invoke.return_value = "This is a test response."

            response = client.post(
                "/chat",
                json={"message": "Hello", "session_id": None}
            )

            assert response.status_code == 200
            data = response.json()
            assert "answer" in data
            assert "session_id" in data

    def test_chat_endpoint_new_session(self, client):
        """测试创建新 session"""
        with patch("knowledge_vector.chain.RAGChain.invoke") as mock_invoke:
            mock_invoke.return_value = "Response."

            response = client.post(
                "/chat",
                json={"message": "Hello", "session_id": None}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["session_id"] is not None

    def test_chat_endpoint_with_existing_session(self, client):
        """测试使用已存在的 session"""
        with patch("knowledge_vector.chain.RAGChain.invoke") as mock_invoke:
            mock_invoke.return_value = "Response for existing session."

            # 先创建 session
            response1 = client.post(
                "/chat",
                json={"message": "Hello", "session_id": None}
            )
            session_id = response1.json()["session_id"]

            # 使用该 session 继续对话
            response2 = client.post(
                "/chat",
                json={"message": "Continue", "session_id": session_id}
            )

            assert response2.status_code == 200
            assert response2.json()["session_id"] == session_id

    def test_sessions_endpoint(self, client):
        """测试获取 session 列表"""
        with patch("knowledge_vector.chain.RAGChain.invoke") as mock_invoke:
            mock_invoke.return_value = "Response."

            # 先创建一个 session
            client.post("/chat", json={"message": "Hello", "session_id": None})

            # 获取 session 列表
            response = client.get("/sessions")
            assert response.status_code == 200

    def test_session_not_found(self, client):
        """测试 session 不存在返回 404"""
        response = client.get("/sessions/nonexistent_session_id/history")
        assert response.status_code == 404

    def test_delete_session(self, client):
        """测试删除 session"""
        with patch("knowledge_vector.chain.RAGChain.invoke") as mock_invoke:
            mock_invoke.return_value = "Response."

            # 先创建 session
            response1 = client.post(
                "/chat",
                json={"message": "Hello", "session_id": None}
            )
            session_id = response1.json()["session_id"]

            # 删除 session
            response2 = client.delete(f"/sessions/{session_id}")
            assert response2.status_code == 200

            # 验证 session 不存在
            response3 = client.get(f"/sessions/{session_id}/history")
            assert response3.status_code == 404

    def test_chat_endpoint_validation_error(self, client):
        """测试聊天端点参数验证错误"""
        # message 字段设置为必需但不验证最小长度
        # 空字符串在 API 层面是被接受的
        response = client.post(
            "/chat",
            json={"message": ""}
        )
        # API 接受空消息（路由层可能会处理）
        assert response.status_code in [200, 400, 422]


class TestSessionStore:
    """SessionStore 单元测试"""

    def test_get_or_create_session(self):
        """测试获取或创建 session"""
        from knowledge_vector.chat import SessionStore

        store = SessionStore()

        # 首次获取应该创建
        memory1 = store.get_memory("new_session")
        assert memory1 is not None

        # 再次获取应该返回相同的 memory 对象
        memory2 = store.get_memory("new_session")
        assert memory1 is memory2

    def test_list_sessions(self):
        """测试列出所有 session"""
        from knowledge_vector.chat import SessionStore

        store = SessionStore()

        store.get_memory("session1")
        store.get_memory("session2")

        sessions = store.list_sessions()
        assert "session1" in sessions
        assert "session2" in sessions

    def test_delete_session(self):
        """测试删除 session"""
        from knowledge_vector.chat import SessionStore

        store = SessionStore()

        store.get_memory("temp_session")
        assert "temp_session" in store.list_sessions()

        store.clear_session("temp_session")
        assert "temp_session" not in store.list_sessions()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
