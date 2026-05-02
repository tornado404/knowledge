"""单元测试 - ConversationMemory"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "kgsrc"))

from knowledge_vector.memory import ConversationMemory, ChatMessage


class TestConversationMemory:
    """ConversationMemory 单元测试"""

    def test_add_user(self):
        """测试添加用户消息"""
        memory = ConversationMemory()
        memory.add_user("Hello")
        assert len(memory.messages) == 1
        assert memory.messages[0].role == "user"
        assert memory.messages[0].content == "Hello"

    def test_add_assistant(self):
        """测试添加助手消息"""
        memory = ConversationMemory()
        memory.add_assistant("Hi there!")
        assert len(memory.messages) == 1
        assert memory.messages[0].role == "assistant"
        assert memory.messages[0].content == "Hi there!"

    def test_add_message(self):
        """测试通用添加消息方法"""
        memory = ConversationMemory()
        memory.add_message("user", "Test message")
        assert len(memory.messages) == 1
        assert memory.messages[0].role == "user"

    def test_get_history(self):
        """测试获取对话历史（List[dict] 格式）"""
        memory = ConversationMemory()
        memory.add_user("Question 1")
        memory.add_assistant("Answer 1")
        memory.add_user("Question 2")

        history = memory.get_history()
        assert isinstance(history, list)
        assert len(history) == 3
        assert history[0] == {"role": "user", "content": "Question 1"}
        assert history[1] == {"role": "assistant", "content": "Answer 1"}
        assert history[2] == {"role": "user", "content": "Question 2"}

    def test_get_history_limited_by_max_turns(self):
        """测试对话历史受 max_turns 限制"""
        memory = ConversationMemory(max_turns=2)

        # 添加 6 条消息（3 轮对话）
        memory.add_user("Q1")
        memory.add_assistant("A1")
        memory.add_user("Q2")
        memory.add_assistant("A2")
        memory.add_user("Q3")
        memory.add_assistant("A3")

        # 应该只保留最近 2 轮（4 条消息）
        history = memory.get_history()
        assert len(history) == 4

    def test_get_history_empty(self):
        """测试空历史返回空列表"""
        memory = ConversationMemory()
        history = memory.get_history()
        assert history == []

    def test_get_history_text(self):
        """测试获取格式化的对话历史文本"""
        memory = ConversationMemory()
        memory.add_user("Hello")
        memory.add_assistant("Hi there!")

        text = memory.get_history_text()
        assert "用户: Hello" in text
        assert "助手: Hi there!" in text

    def test_get_history_for_rag(self):
        """测试获取 RAG 使用的对话历史"""
        memory = ConversationMemory()
        memory.add_user("Hello")
        memory.add_assistant("Hi there!")

        text = memory.get_history_for_rag()
        assert "用户: Hello" in text
        assert "助手: Hi there!" in text

    def test_turn_count(self):
        """测试对话轮数计算"""
        memory = ConversationMemory()
        assert memory.turn_count == 0

        memory.add_user("Q1")
        memory.add_assistant("A1")
        assert memory.turn_count == 1

        memory.add_user("Q2")
        memory.add_assistant("A2")
        assert memory.turn_count == 2

    def test_clear(self):
        """测试清空对话历史"""
        memory = ConversationMemory()
        memory.add_user("Hello")
        memory.add_assistant("Hi!")

        memory.clear()
        assert len(memory.messages) == 0
        assert memory.is_empty is True

    def test_is_empty(self):
        """测试 is_empty 属性"""
        memory = ConversationMemory()
        assert memory.is_empty is True

        memory.add_user("Hello")
        assert memory.is_empty is False

    def test_get_messages(self):
        """测试获取所有消息"""
        memory = ConversationMemory()
        memory.add_user("Hello")
        memory.add_assistant("Hi!")

        messages = memory.get_messages()
        assert len(messages) == 2
        assert isinstance(messages[0], ChatMessage)

    def test_get_recent_messages(self):
        """测试获取最近 n 条消息"""
        memory = ConversationMemory()
        for i in range(5):
            memory.add_user(f"Q{i}")

        recent = memory.get_recent_messages(2)
        assert len(recent) == 2
        assert recent[0].content == "Q3"

    def test_len(self):
        """测试 len() 方法"""
        memory = ConversationMemory()
        assert len(memory) == 0

        memory.add_user("Hello")
        assert len(memory) == 1

        memory.add_assistant("Hi!")
        assert len(memory) == 2

    def test_repr(self):
        """测试 __repr__ 方法"""
        memory = ConversationMemory(max_turns=5)
        repr_str = repr(memory)
        assert "ConversationMemory" in repr_str
        assert "turns=0" in repr_str


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
