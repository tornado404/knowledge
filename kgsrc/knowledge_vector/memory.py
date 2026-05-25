"""Conversation Memory - 对话历史管理器"""

from dataclasses import dataclass, field
from typing import List, Optional, Callable, Tuple
from datetime import datetime
import re


# Token 估算常量
CHINESE_CHARS_PATTERN = re.compile(r'[一-鿿]')


def estimate_tokens(text: str) -> int:
    """估算文本的 token 数量（统一实现）

    使用公式：中文约 1.5 tokens/字，英文约 4 chars/token
    实际 tokenization 时，英文约 4 字符 = 1 token

    Args:
        text: 输入文本

    Returns:
        估算的 token 数量
    """
    if not text:
        return 0
    chinese_chars = len(CHINESE_CHARS_PATTERN.findall(text))
    other_chars = len(text) - chinese_chars
    return int(chinese_chars * 1.5 + other_chars * 0.25)


@dataclass
class ChatMessage:
    """单条对话消息"""
    role: str  # "user" or "assistant"
    content: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class MessageSummary:
    """消息摘要"""
    content: str  # 摘要内容
    original_count: int  # 摘要的消息数量
    first_msg_time: str  # 首条消息时间
    last_msg_time: str  # 末条消息时间


class CompressionCallback:
    """压缩回调接口"""

    def on_compress(self, stats: dict):
        """压缩完成后的回调

        Args:
            stats: 压缩统计信息
        """
        pass


class AutoCompressPolicy:
    """自动压缩策略

    属性:
        ON_EVERY_ADD: 每次添加消息后检查压缩
        EVERY_N_TURNS: 每 N 轮对话后检查压缩
        MANUAL_ONLY: 仅手动触发压缩
    """

    ON_EVERY_ADD = "on_every_add"
    EVERY_N_TURNS = "every_n_turns"
    MANUAL_ONLY = "manual_only"

    def __init__(self, policy: str = ON_EVERY_ADD, n_turns: int = 5):
        """初始化策略

        Args:
            policy: 策略类型
            n_turns: 当 policy=EVERY_N_TURNS 时的轮数间隔
        """
        self.policy = policy
        self.n_turns = n_turns
        self._turns_since_compression = 0

    def should_compress(self, turn_count: int) -> bool:
        """判断是否应该触发压缩检查

        Args:
            turn_count: 当前对话轮数

        Returns:
            是否应该触发压缩
        """
        if self.policy == self.ON_EVERY_ADD:
            return True
        elif self.policy == self.EVERY_N_TURNS:
            self._turns_since_compression += 1
            if self._turns_since_compression >= self.n_turns:
                self._turns_since_compression = 0
                return True
        # MANUAL_ONLY: 始终返回 False
        return False

    def reset(self):
        """重置策略状态"""
        self._turns_since_compression = 0

    @classmethod
    def from_string(cls, policy_str: str) -> "AutoCompressPolicy":
        """从字符串创建策略实例

        Args:
            policy_str: 策略字符串 (on_every_add, every_n_turns, manual_only)

        Returns:
            AutoCompressPolicy 实例
        """
        if policy_str == cls.ON_EVERY_ADD:
            return cls(policy=cls.ON_EVERY_ADD)
        elif policy_str == cls.MANUAL_ONLY:
            return cls(policy=cls.MANUAL_ONLY)
        elif policy_str.startswith(cls.EVERY_N_TURNS):
            # 支持格式: "every_n_turns:5"
            parts = policy_str.split(":")
            n = int(parts[1]) if len(parts) > 1 else 5
            return cls(policy=cls.EVERY_N_TURNS, n_turns=n)
        return cls()


class ConversationMemory:
    """对话历史管理器

    支持两种压缩模式:
    1. 截断模式 (truncation): 简单保留最近 N 轮对话
    2. 摘要模式 (summarization): 对旧对话进行摘要压缩，保留完整最近对话

    压缩统计:
    - compression_count: 压缩次数
    - compressed_tokens: 累计压缩的 token 数
    - original_messages: 累计处理的消息数

    支持压缩回调，可在压缩发生时执行自定义操作。
    """

    # 默认 token 预算 (保守估计 4K context window)
    DEFAULT_TOKEN_BUDGET = 3000
    # 最大摘要历史条数
    MAX_SUMMARY_HISTORY = 10

    def __init__(
        self,
        max_turns: int = 10,
        compression_threshold: int = 5,
        use_summarization: bool = True,
        summarizer_fn: Optional[Callable[[List[ChatMessage]], str]] = None,
        token_budget: int = DEFAULT_TOKEN_BUDGET,
        max_summary_history: int = MAX_SUMMARY_HISTORY,
        compression_callback: Optional[CompressionCallback] = None,
    ):
        """初始化对话历史管理器

        Args:
            max_turns: 最大保存的对话轮数（每轮=用户+助手）
            compression_threshold: 开始压缩的轮数阈值
            use_summarization: 是否使用摘要压缩（True=摘要模式，False=截断模式）
            summarizer_fn: 自定义摘要函数，接收消息列表返回摘要字符串
            token_budget: Token 预算，用于智能截断
            max_summary_history: 最大保留的摘要历史条数
            compression_callback: 压缩完成后的回调函数
        """
        self.messages: List[ChatMessage] = []
        self.max_turns = max_turns
        self.compression_threshold = compression_threshold
        self.use_summarization = use_summarization
        self.summarizer_fn = summarizer_fn
        self.token_budget = token_budget
        self.max_summary_history = max_summary_history
        self.compression_callback = compression_callback

        # 摘要历史 - 存储被压缩的旧消息摘要
        self._summary_history: List[MessageSummary] = []

        # 压缩统计
        self.compression_count: int = 0
        self.compressed_tokens: int = 0
        self.original_message_count: int = 0

    def _should_compress(self) -> bool:
        """检查是否应该压缩

        触发条件（满足任一即可）：
        1. Token 预算超限：当前消息总 token 超过 token_budget * 0.8
        2. 消息数量超限：消息数超过 (max_turns + compression_threshold) * 2
        """
        # 只在一轮对话结束后检查（消息数为偶数）
        if len(self.messages) % 2 != 0:
            return False

        # 检查 token 预算
        total_text = "\n".join(m.content for m in self.messages)
        total_tokens = estimate_tokens(total_text)
        if total_tokens > self.token_budget * 0.8:
            return True

        # 检查消息数量
        max_messages = (self.max_turns + self.compression_threshold) * 2
        if len(self.messages) <= max_messages:
            return False

        # 检查是否有足够的旧消息值得压缩
        compressible = len(self.messages) - (self.max_turns * 2)
        return compressible >= 2

    def _compress_via_truncation(self) -> List[ChatMessage]:
        """通过截断获取压缩后的消息（保留最近 max_turns 轮）"""
        recent_count = self.max_turns * 2
        return self.messages[-recent_count:] if len(self.messages) > recent_count else self.messages

    def _compress_via_summarization(self, incremental: bool = True) -> Tuple[List[ChatMessage], str]:
        """通过摘要压缩旧消息

        保留策略：优先保证 token 预算内保留完整对话，其次保留最新消息

        Args:
            incremental: 是否增量压缩。True=只压缩超出 budget 的部分，False=全量压缩到 max_turns

        Returns:
            (recent_messages, summary_text) - 保留的消息和历史摘要
        """
        recent_count = self.max_turns * 2
        budget = self.token_budget * 0.8  # 保留 20% 空间给摘要

        # 如果消息数未超限，直接返回
        if len(self.messages) < recent_count:
            return self.messages, ""

        if incremental:
            # 增量压缩：只压缩超出 budget 的部分
            retained_messages = []
            retained_tokens = 0

            # 从最新消息开始，优先保留
            for msg in reversed(self.messages):
                msg_tokens = estimate_tokens(msg.content)
                if retained_tokens + msg_tokens <= budget:
                    retained_messages.insert(0, msg)
                    retained_tokens += msg_tokens
                else:
                    break

            # 如果保留的消息为空，只保留最后一条
            if not retained_messages:
                retained_messages = [self.messages[-1]]
        else:
            # 全量压缩：保留最近的 recent_count 条消息
            retained_messages = self.messages[-recent_count:]

        # 对被裁剪的旧消息进行摘要
        retained_ids = {id(m) for m in retained_messages}
        old_messages = [m for m in self.messages if id(m) not in retained_ids]

        if not old_messages:
            return retained_messages, ""

        # 生成摘要
        if self.summarizer_fn:
            summary_text = self.summarizer_fn(old_messages)
        else:
            summary_text = self._default_summarize(old_messages)

        return retained_messages, summary_text

    def _default_summarize(self, messages: List[ChatMessage]) -> str:
        """默认摘要生成（模板方式，不依赖 LLM）

        改进：保留语义完整性，提取关键问题和答案对
        """
        if not messages:
            return ""

        # 提取关键信息
        user_msgs = [(i, m) for i, m in enumerate(messages) if m.role == "user"]
        assistant_msgs = [(i, m) for i, m in enumerate(messages) if m.role == "assistant"]

        summary_parts = []

        # 统计信息
        if len(user_msgs) > 0:
            summary_parts.append(f"用户共提问 {len(user_msgs)} 个问题")
        if len(assistant_msgs) > 0:
            summary_parts.append(f"助手回复 {len(assistant_msgs)} 次")

        # 保留关键问题和回答（首尾 + 中间抽样）
        key_pairs = []

        # 首轮完整内容（最重要）
        if user_msgs and assistant_msgs:
            first_user = user_msgs[0][1].content
            first_assistant = assistant_msgs[0][1].content
            # 截断但保留核心
            first_user_snippet = first_user[:100] + "..." if len(first_user) > 100 else first_user
            first_assistant_snippet = first_assistant[:100] + "..." if len(first_assistant) > 100 else first_assistant
            key_pairs.append(f"首问：{first_user_snippet}")
            key_pairs.append(f"首答：{first_assistant_snippet}")

        # 最后一轮（最近的上下文）
        if len(user_msgs) > 1 and len(assistant_msgs) > 1:
            last_user = user_msgs[-1][1].content
            last_assistant = assistant_msgs[-1][1].content
            last_user_snippet = last_user[:80] + "..." if len(last_user) > 80 else last_user
            last_assistant_snippet = last_assistant[:80] + "..." if len(last_assistant) > 80 else last_assistant
            key_pairs.append(f"近问：{last_user_snippet}")
            key_pairs.append(f"近答：{last_assistant_snippet}")

        # 中间轮次抽样（如果对话较长）
        if len(user_msgs) > 3:
            mid_idx = len(user_msgs) // 2
            mid_user = user_msgs[mid_idx][1].content
            mid_user_snippet = mid_user[:60] + "..." if len(mid_user) > 60 else mid_user
            key_pairs.append(f"中问：{mid_user_snippet}")

        summary_parts.extend(key_pairs)

        return "；".join(summary_parts)

    def _build_compressed_context(self) -> str:
        """构建压缩后的完整上下文"""
        if self.use_summarization and self._summary_history:
            # 构建摘要历史
            summary_parts = []
            for s in self._summary_history:
                summary_parts.append(f"[早期对话({s.original_count}条)] {s.content}")

            if summary_parts:
                return "\n".join(summary_parts) + "\n\n--- 最近对话 ---\n"
        return ""

    def add_user(self, content: str) -> None:
        """添加用户消息"""
        self.messages.append(ChatMessage(role="user", content=content))

    def add_assistant(self, content: str) -> None:
        """添加助手消息"""
        self.messages.append(ChatMessage(role="assistant", content=content))

    def add_message(self, role: str, content: str) -> None:
        """添加消息（通用方法）

        Args:
            role: "user" or "assistant"
            content: 消息内容
        """
        self.messages.append(ChatMessage(role=role, content=content))

    def get_history(self) -> List[dict]:
        """获取对话历史（格式：List[dict]）

        Returns:
            [{"role": "user"/"assistant", "content": "..."}]
        """
        if not self.messages:
            return []

        # 使用当前消息（已压缩后）
        return [{"role": msg.role, "content": msg.content} for msg in self.messages]

    def get_history_text(self) -> str:
        """获取格式化的对话历史文本

        Returns:
            格式化的历史字符串，格式：
            用户: xxx
            助手: xxx
            用户: xxx
        """
        if not self.messages and not self._summary_history:
            return "（无历史对话）"

        budget = self.token_budget * 0.8
        result_parts = []
        result_tokens = 0

        # 添加摘要历史
        if self.use_summarization and self._summary_history:
            for s in self._summary_history:
                summary_text = "【对话摘要】" + s.content
                summary_tokens = estimate_tokens(summary_text)
                if result_tokens + summary_tokens <= budget:
                    result_parts.append(summary_text)
                    result_tokens += summary_tokens

        # 添加消息
        for msg in self.messages:
            role_cn = "用户" if msg.role == "user" else "助手"
            msg_text = f"{role_cn}: {msg.content}"
            msg_tokens = estimate_tokens(msg_text)
            if result_tokens + msg_tokens <= budget:
                result_parts.append(msg_text)
                result_tokens += msg_tokens
            else:
                break

        return "\n".join(result_parts) if result_parts else "（无历史对话）"

    def get_history_for_rag(self) -> str:
        """获取适合 RAG 使用的对话历史

        智能策略：
        1. 优先使用摘要（摘要是压缩后的核心信息）
        2. 如果摘要太大，逐步截断摘要直到能放入预算
        3. 如果没有摘要或摘要为空，使用最新消息
        """
        if not self.messages and not self._summary_history:
            return ""

        budget = self.token_budget * 0.8
        result_parts = []
        result_tokens = 0

        # 如果有摘要，优先使用摘要
        if self.use_summarization and self._summary_history:
            summary_parts = []
            for s in self._summary_history:
                summary_parts.append("【历史摘要】" + s.content)

            # 尝试包含所有摘要
            for part in summary_parts:
                part_tokens = estimate_tokens(part)
                if result_tokens + part_tokens <= budget:
                    result_parts.append(part)
                    result_tokens += part_tokens
                elif result_tokens == 0:
                    # 摘要太大，截断它
                    truncated = self._truncate_text_by_token(part, budget)
                    if truncated:
                        result_parts.append(truncated)
                        result_tokens = estimate_tokens(truncated)
                    break
                else:
                    break

            # 如果已经放入了一些内容，检查是否可以添加消息
            if result_tokens > 0:
                remaining_budget = budget - result_tokens
                # 限制只取最近 max_turns 轮的消息
                recent_messages = self.messages[-(self.max_turns * 2):]
                for msg in recent_messages:
                    role_cn = "用户" if msg.role == "user" else "助手"
                    msg_text = role_cn + ": " + msg.content
                    msg_tokens = estimate_tokens(msg_text)
                    if msg_tokens <= remaining_budget:
                        result_parts.append(msg_text)
                        result_tokens += msg_tokens
                        remaining_budget -= msg_tokens
                    else:
                        break

            return "\n".join(result_parts) if result_parts else ""

        # 没有摘要时，直接使用消息（限制为最近 max_turns 轮）
        recent_messages = self.messages[-(self.max_turns * 2):]
        for msg in recent_messages:
            role_cn = "用户" if msg.role == "user" else "助手"
            msg_text = role_cn + ": " + msg.content
            msg_tokens = estimate_tokens(msg_text)
            if result_tokens + msg_tokens <= budget:
                result_parts.append(msg_text)
                result_tokens += msg_tokens
            else:
                break

        return "\n".join(result_parts) if result_parts else ""

    def _truncate_text_by_token(self, text: str, max_tokens: int) -> str:
        """截断文本到指定 token 数"""
        tokens = estimate_tokens(text)
        if tokens <= max_tokens:
            return text

        # 二分查找最大可接受的字符数
        low, high = 0, len(text)
        while low < high:
            mid = (low + high + 1) // 2
            if estimate_tokens(text[:mid]) <= max_tokens:
                low = mid
            else:
                high = mid - 1
        return text[:low] + "..."

    def get_history_with_summary(self) -> Tuple[List[dict], str]:
        """获取对话历史和摘要

        Returns:
            (messages_list, summary_text) - 消息列表和历史摘要
        """
        if not self.messages:
            return [], ""

        messages = [{"role": msg.role, "content": msg.content} for msg in self.messages]

        if self.use_summarization and self._summary_history:
            summary_parts = [s.content for s in self._summary_history]
            return messages, "\n".join(summary_parts)

        return messages, ""

    def get_compressed_context(self) -> str:
        """获取压缩后的完整上下文（包含摘要历史）"""
        return self._build_compressed_context()

    def get_summary_context(self) -> str:
        """获取仅包含摘要历史的上下文（不包含最近消息）

        用于 agent 的 system prompt，让 LLM 了解之前的对话摘要
        """
        if not self._summary_history:
            return ""

        parts = []
        for s in self._summary_history:
            parts.append(f"【早期对话摘要】{s.content}")

        return "\n\n".join(parts)

    def compress(self, incremental: bool = True) -> bool:
        """触发压缩（将当前消息压缩为摘要）

        Args:
            incremental: 是否增量压缩。True=只压缩超出预算的部分，False=全量压缩到 max_turns

        Returns:
            是否实际执行了压缩
        """
        if not self.use_summarization:
            return False  # 截断模式不需要压缩

        if not self._should_compress():
            return False

        # 使用基于 token 的智能压缩
        retained_messages, summary_content = self._compress_via_summarization(incremental=incremental)

        if not retained_messages:
            return False

        # 如果有旧消息需要压缩
        old_messages = [m for m in self.messages if id(m) not in {id(m2) for m2 in retained_messages}]

        if old_messages and summary_content:
            # 统计信息
            old_tokens = sum(estimate_tokens(m.content) for m in old_messages)
            self.compressed_tokens += old_tokens
            self.original_message_count += len(old_messages)
            self.compression_count += 1

            # 保存摘要（限制数量）
            summary = MessageSummary(
                content=summary_content,
                original_count=len(old_messages),
                first_msg_time=old_messages[0].timestamp,
                last_msg_time=old_messages[-1].timestamp,
            )
            self._summary_history.append(summary)

            # 限制摘要历史数量
            while len(self._summary_history) > self.max_summary_history:
                self._summary_history.pop(0)

        # 保留消息
        self.messages = retained_messages

        # 调用压缩回调
        if self.compression_callback:
            self.compression_callback.on_compress(self.get_compression_stats())

        # 只有实际发生了压缩才返回 True
        return bool(old_messages and summary_content)

    def clear(self, clear_stats: bool = False) -> None:
        """清空对话历史

        Args:
            clear_stats: 是否同时清除压缩统计
        """
        self.messages = []
        self._summary_history = []
        if clear_stats:
            self.compression_count = 0
            self.compressed_tokens = 0
            self.original_message_count = 0

    def get_summary_history(self) -> List[MessageSummary]:
        """获取所有历史摘要"""
        return self._summary_history.copy()

    @property
    def turn_count(self) -> int:
        """获取当前对话轮数"""
        return len(self.messages) // 2

    @property
    def total_turn_count(self) -> int:
        """获取总对话轮数（包括已压缩的）"""
        compressed_turns = self.original_message_count // 2
        return compressed_turns + self.turn_count

    def get_compression_stats(self) -> dict:
        """获取压缩统计信息

        Returns:
            包含压缩统计的字典
        """
        return {
            "compression_count": self.compression_count,
            "compressed_tokens": self.compressed_tokens,
            "original_message_count": self.original_message_count,
            "current_message_count": len(self.messages),
            "summary_history_count": len(self._summary_history),
            "compression_rate": (
                f"{self.compressed_tokens / max(1, self.original_message_count):.1f} tokens/msg"
                if self.original_message_count > 0 else "N/A"
            ),
        }

    @property
    def is_empty(self) -> bool:
        """检查是否为空"""
        return len(self.messages) == 0 and len(self._summary_history) == 0

    def get_messages(self) -> List[ChatMessage]:
        """获取所有消息"""
        return self.messages.copy()

    def get_recent_messages(self, n: int) -> List[ChatMessage]:
        """获取最近 n 条消息"""
        return self.messages[-n:] if self.messages else []

    def __len__(self) -> int:
        return len(self.messages)

    def __repr__(self) -> str:
        return f"ConversationMemory(turns={self.turn_count}, total_turns={self.total_turn_count}, messages={len(self.messages)}, summaries={len(self._summary_history)})"


# ========== Multi-Agent 上下文支持 ==========

class AgentContext:
    """多 Agent 上下文"""

    def __init__(self, agent_id: str, agent_type: str):
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.data: dict = {}

    def set(self, key: str, value: any):
        self.data[key] = value

    def get(self, key: str, default: any = None) -> any:
        return self.data.get(key, default)

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "data": self.data
        }


class MultiAgentContext:
    """多 Agent 会话上下文管理器

    支持上下文压缩功能，可配置:
    - max_turns: 最大保存的对话轮数
    - compression_threshold: 开始压缩的阈值
    - use_summarization: 是否使用摘要压缩
    - max_summary_history: 最大摘要历史条数
    - compression_callback: 压缩回调
    """

    def __init__(
        self,
        max_turns: int = 10,
        compression_threshold: int = 5,
        use_summarization: bool = True,
        max_summary_history: int = ConversationMemory.MAX_SUMMARY_HISTORY,
        compression_callback: Optional[CompressionCallback] = None,
    ):
        self.memory = ConversationMemory(
            max_turns=max_turns,
            compression_threshold=compression_threshold,
            use_summarization=use_summarization,
            max_summary_history=max_summary_history,
            compression_callback=compression_callback,
        )
        self.agent_contexts: dict[str, AgentContext] = {}
        self.task_results: dict[str, dict] = {}

    def add_user(self, content: str):
        """添加用户消息"""
        self.memory.add_user(content)

    def add_assistant(self, content: str):
        """添加助手消息"""
        self.memory.add_assistant(content)

    def get_history(self) -> List[dict]:
        """获取对话历史"""
        return self.memory.get_history()

    def get_history_for_rag(self) -> str:
        """获取 RAG 格式历史"""
        return self.memory.get_history_for_rag()

    def get_history_with_summary(self) -> Tuple[List[dict], str]:
        """获取对话历史和摘要"""
        return self.memory.get_history_with_summary()

    def get_compressed_context(self) -> str:
        """获取压缩后的完整上下文"""
        return self.memory.get_compressed_context()

    def compress(self):
        """手动触发压缩"""
        self.memory.compress()

    def register_agent(self, agent_id: str, agent_type: str) -> AgentContext:
        """注册 Agent 上下文"""
        ctx = AgentContext(agent_id, agent_type)
        self.agent_contexts[agent_id] = ctx
        return ctx

    def get_agent_context(self, agent_id: str) -> AgentContext:
        """获取 Agent 上下文"""
        return self.agent_contexts.get(agent_id)

    def set_task_result(self, task_id: str, result: dict):
        """存储任务结果"""
        self.task_results[task_id] = result

    def get_task_result(self, task_id: str) -> dict:
        """获取任务结果"""
        return self.task_results.get(task_id)

    def clear(self):
        """清空所有上下文"""
        self.memory.clear()
        self.agent_contexts.clear()
        self.task_results.clear()

    @property
    def turn_count(self) -> int:
        return self.memory.turn_count

    @property
    def total_turn_count(self) -> int:
        return self.memory.total_turn_count

    def get_summary_history(self) -> List[MessageSummary]:
        """获取历史摘要列表"""
        return self.memory.get_summary_history()

    def get_summary_context(self) -> str:
        """获取仅包含摘要历史的上下文（用于 agent system prompt）"""
        return self.memory.get_summary_context()

    def get_compression_stats(self) -> dict:
        """获取压缩统计信息"""
        return self.memory.get_compression_stats()
