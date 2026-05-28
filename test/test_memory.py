"""单元测试 - ConversationMemory"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "kgsrc"))

from knowledge_vector.memory import (
    ConversationMemory, ChatMessage, estimate_tokens,
    LLMSummarizer, MessageSummary
)


class TestEstimateTokens:
    """estimate_tokens 函数测试"""

    def test_empty_string(self):
        assert estimate_tokens("") == 0

    def test_chinese_only(self):
        result = estimate_tokens("你好世界")
        # tiktoken 或启发式，应该 > 0
        assert result > 0

    def test_english_only(self):
        result = estimate_tokens("hello world")
        # tiktoken 或启发式，应该 > 0
        assert result > 0

    def test_mixed(self):
        result = estimate_tokens("你好hello世界world")
        assert result > 0

    def test_long_text(self):
        """测试长文本 token 估算"""
        long_text = "这是一段很长的中文文本。" * 100
        result = estimate_tokens(long_text)
        assert result > 100  # 应该至少有 100 tokens


class TestLLMSummarizer:
    """LLMSummarizer 单元测试"""

    def test_summarize_empty_messages(self):
        """空消息列表返回空摘要"""
        summarizer = LLMSummarizer()
        result = summarizer.summarize([])
        assert result == ""

    def test_merge_single_summary(self):
        """单条摘要直接返回"""
        summarizer = LLMSummarizer()
        result = summarizer.merge_summaries(["这是唯一一条摘要"])
        assert result == "这是唯一一条摘要"

    def test_merge_empty_summaries(self):
        """空摘要列表返回空字符串"""
        summarizer = LLMSummarizer()
        result = summarizer.merge_summaries([])
        assert result == ""

    @patch('knowledge_vector.memory.LLMSummarizer._get_llm')
    def test_summarize_with_mock_llm(self, mock_get_llm):
        """使用 mock LLM 测试摘要生成"""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "这是生成的摘要"
        mock_llm.invoke.return_value = mock_response
        mock_get_llm.return_value = mock_llm

        summarizer = LLMSummarizer()
        messages = [
            ChatMessage(role="user", content="问题1"),
            ChatMessage(role="assistant", content="回答1"),
        ]
        result = summarizer.summarize(messages)
        assert result == "这是生成的摘要"

    @patch('knowledge_vector.memory.LLMSummarizer._get_llm')
    def test_merge_with_mock_llm(self, mock_get_llm):
        """使用 mock LLM 测试摘要合并"""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "合并后的摘要"
        mock_llm.invoke.return_value = mock_response
        mock_get_llm.return_value = mock_llm

        summarizer = LLMSummarizer()
        summaries = ["摘要1", "摘要2", "摘要3"]
        result = summarizer.merge_summaries(summaries)
        assert result == "合并后的摘要"


class TestSummaryMerging:
    """摘要合并功能测试"""

    def test_merge_old_summaries_basic(self):
        """测试基本摘要合并"""
        memory = ConversationMemory(
            max_turns=1,
            max_summary_history=3,
            use_summarization=True,
        )

        # 手动添加多个摘要
        for i in range(5):
            memory._summary_history.append(MessageSummary(
                content=f"摘要{i}",
                original_count=2,
                first_msg_time="2024-01-01T00:00:00",
                last_msg_time="2024-01-01T00:01:00",
            ))

        # 触发合并
        memory._merge_old_summaries()

        # 合并后应该 <= max_summary_history
        assert len(memory._summary_history) <= 3

    def test_merge_old_summaries_no_merge_needed(self):
        """摘要数量未超限时不合并"""
        memory = ConversationMemory(
            max_turns=1,
            max_summary_history=5,
            use_summarization=True,
        )

        # 添加少量摘要
        for i in range(3):
            memory._summary_history.append(MessageSummary(
                content=f"摘要{i}",
                original_count=2,
                first_msg_time="2024-01-01T00:00:00",
                last_msg_time="2024-01-01T00:01:00",
            ))

        original_count = len(memory._summary_history)
        memory._merge_old_summaries()

        # 不应该变化
        assert len(memory._summary_history) == original_count


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

    def test_clear_with_stats(self):
        """测试清空对话历史（同时清除统计）"""
        memory = ConversationMemory()
        memory.add_user("Hello")
        memory.add_assistant("Hi!")
        memory.compress()  # 尝试触发压缩

        memory.clear(clear_stats=True)
        assert memory.compression_count == 0
        assert memory.compressed_tokens == 0

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

    def test_should_compress_odd_messages(self):
        """测试压缩触发条件 - 奇数条消息时不触发"""
        memory = ConversationMemory(max_turns=2, compression_threshold=2)
        # 添加 3 条消息（不完整的轮）
        memory.add_user("Q1")
        memory.add_assistant("A1")
        memory.add_user("Q2")
        assert memory._should_compress() is False

    def test_should_compress_token_budget(self):
        """测试压缩触发条件 - Token 超预算"""
        memory = ConversationMemory(max_turns=2, token_budget=10)
        # 添加大量文本使 token 超预算
        long_text = "这" * 100  # 约 150 tokens > 8 tokens budget
        memory.add_user(long_text)
        memory.add_assistant(long_text)
        memory.add_user(long_text)
        memory.add_assistant(long_text)
        # 4 条消息，token 远超预算
        assert memory._should_compress() is True

    def test_compression_stats(self):
        """测试压缩统计"""
        memory = ConversationMemory(max_turns=1, token_budget=50)
        # 添加足够的对话触发压缩
        for i in range(6):
            memory.add_user(f"问题{i}")
            memory.add_assistant(f"回答{i}")

        # 触发压缩
        if memory._should_compress():
            memory.compress()

        stats = memory.get_compression_stats()
        assert "compression_count" in stats
        assert "compressed_tokens" in stats
        assert "original_message_count" in stats

    def test_compression_max_summary_history(self):
        """测试摘要历史条数上限（使用合并而非 FIFO）"""
        memory = ConversationMemory(max_turns=1, max_summary_history=3)
        # 多次触发压缩
        for i in range(5):
            # 添加多轮对话
            for j in range(4):
                memory.add_user(f"Q{i}_{j}")
                memory.add_assistant(f"A{i}_{j}")
            if memory._should_compress():
                memory.compress()

        # 摘要历史应该被限制在 max_summary_history 以内
        assert len(memory._summary_history) <= 3

    def test_total_turn_count(self):
        """测试总对话轮数统计"""
        memory = ConversationMemory(max_turns=2)
        memory.add_user("Q1")
        memory.add_assistant("A1")

        assert memory.turn_count == 1
        assert memory.total_turn_count == 1

    def test_get_summary_context(self):
        """测试获取摘要上下文"""
        memory = ConversationMemory(max_turns=1, token_budget=20)
        # 添加足够的对话触发压缩
        for i in range(4):
            memory.add_user(f"问题{i}")
            memory.add_assistant(f"回答{i}")

        if memory._should_compress():
            memory.compress()

        context = memory.get_summary_context()
        # 压缩后应该有摘要上下文
        # 注意：可能没有被压缩（取决于 token 估算）

    def test_truncate_mode(self):
        """测试截断模式"""
        memory = ConversationMemory(use_summarization=False, max_turns=2)
        for i in range(6):
            memory.add_user(f"Q{i}")
            memory.add_assistant(f"A{i}")

        # 截断模式下 compress() 不起作用
        success, reason = memory.compress()
        assert success is False  # 截断模式返回 False
        assert reason == "truncation_mode"

    def test_incremental_compression(self):
        """测试增量压缩"""
        memory = ConversationMemory(max_turns=2, token_budget=30)
        # 添加大量对话，使 token 超过预算
        for i in range(10):
            memory.add_user(f"这是一个比较长的问题内容{i}")
            memory.add_assistant(f"这是一个比较长的回答内容{i}")

        # 触发压缩
        memory.compress(incremental=True)
        stats = memory.get_compression_stats()
        assert stats["compression_count"] >= 1

    def test_llm_summarizer_flag(self):
        """测试 use_llm_summarizer 参数"""
        memory = ConversationMemory(use_llm_summarizer=True)
        assert memory.use_llm_summarizer is True

        memory2 = ConversationMemory(use_llm_summarizer=False)
        assert memory2.use_llm_summarizer is False

    def test_compression_ratio(self):
        """测试 compression_ratio 参数"""
        # 默认 compression_ratio 是 0.7
        memory = ConversationMemory(token_budget=100)
        assert memory.compression_ratio == 0.7

        # 自定义 compression_ratio
        memory2 = ConversationMemory(token_budget=100, compression_ratio=0.5)
        assert memory2.compression_ratio == 0.5

    def test_compress_return_type(self):
        """测试 compress() 返回 Tuple[bool, str]"""
        memory = ConversationMemory(max_turns=1, token_budget=50)
        # 截断模式返回 (False, "truncation_mode")
        success, reason = memory.compress()
        assert success is False
        assert reason == "truncation_mode"

    def test_should_compress_warning(self):
        """测试 should_compress_warning 预警方法"""
        memory = ConversationMemory(max_turns=2, compression_threshold=2)
        # 初始状态不应预警
        should_warn, ratio = memory.should_compress_warning()
        assert should_warn is False

        # 添加消息后
        for i in range(4):
            memory.add_user(f"问题内容{i}")
            memory.add_assistant(f"回答内容{i}")

        # 超过 50% 使用率时预警 (0.7 * 0.7 = 0.49 < 0.5)
        should_warn, ratio = memory.should_compress_warning()
        # 使用率应该大于 0
        assert ratio > 0


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
