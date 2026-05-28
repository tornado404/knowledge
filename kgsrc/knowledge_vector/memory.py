"""Conversation Memory - 对话历史管理器"""

from dataclasses import dataclass, field
from typing import List, Optional, Callable, Tuple
from datetime import datetime
import re


# ========== Token 估算 ==========

# 尝试使用 tiktoken 精确计数，不可用时回退到启发式
_tiktoken_encoder = None

def _get_tiktoken_encoder():
    """延迟加载 tiktoken encoder"""
    global _tiktoken_encoder
    if _tiktoken_encoder is not None:
        return _tiktoken_encoder
    try:
        import tiktoken
        _tiktoken_encoder = tiktoken.get_encoding("cl100k_base")
        return _tiktoken_encoder
    except Exception:
        return None


CHINESE_CHARS_PATTERN = re.compile(r'[一-鿿]')


def estimate_tokens(text: str) -> int:
    """估算文本的 token 数量

    优先使用 tiktoken 精确计数，不可用时回退到启发式公式。

    Args:
        text: 输入文本

    Returns:
        估算的 token 数量
    """
    if not text:
        return 0

    encoder = _get_tiktoken_encoder()
    if encoder:
        return len(encoder.encode(text))

    # 回退：启发式公式
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


# ========== LLM 摘要生成器 ==========

class LLMSummarizer:
    """基于 LLM 的语义摘要生成器

    使用 ChatAnthropic (MiniMax API) 生成对话摘要，保留关键语义信息。
    """

    SUMMARIZE_PROMPT = """你是一个对话摘要助手。请将以下对话历史压缩成简洁的摘要。

要求：
1. 保留关键信息：用户的问题主题、重要决策、关键概念
2. 摘要长度控制在 200 字以内
3. 使用中文输出
4. 按时间顺序组织信息

对话历史：
{conversation}

请输出摘要："""

    MERGE_PROMPT = """你是一个对话摘要助手。请将以下多条摘要合并成一条连贯的摘要。

要求：
1. 保留所有关键信息，去除重复内容
2. 按时间顺序组织
3. 摘要长度控制在 300 字以内
4. 使用中文输出

摘要列表：
{summaries}

请输出合并后的摘要："""

    def __init__(self, model: str = None, api_key: str = None, base_url: str = None):
        """初始化 LLM 摘要生成器

        Args:
            model: 模型名称，默认使用配置中的模型
            api_key: API Key，默认使用配置中的 key
            base_url: API Base URL，默认使用配置中的 URL
        """
        self._llm = None
        self._model = model
        self._api_key = api_key
        self._base_url = base_url

    def _get_llm(self):
        """延迟加载 LLM"""
        if self._llm is not None:
            return self._llm

        try:
            from langchain_anthropic import ChatAnthropic
            from .config import config

            self._llm = ChatAnthropic(
                model=self._model or config.anthropic_model or "MiniMax-M2.7",
                api_key=self._api_key or config.anthropic_api_key,
                base_url=self._base_url or config.anthropic_base_url,
            )
            return self._llm
        except Exception as e:
            print(f"[LLMSummarizer] Failed to load LLM: {e}")
            return None

    def summarize(self, messages: List["ChatMessage"]) -> str:
        """生成对话摘要

        Args:
            messages: 对话消息列表

        Returns:
            摘要文本
        """
        llm = self._get_llm()
        if not llm or not messages:
            return ""

        # 构建对话文本
        conversation_parts = []
        for msg in messages:
            role_cn = "用户" if msg.role == "user" else "助手"
            # 截断过长的单条消息
            content = msg.content[:500] + "..." if len(msg.content) > 500 else msg.content
            conversation_parts.append(f"{role_cn}: {content}")

        conversation_text = "\n".join(conversation_parts)
        prompt = self.SUMMARIZE_PROMPT.format(conversation=conversation_text)

        try:
            from langchain_core.messages import HumanMessage
            response = llm.invoke([HumanMessage(content=prompt)])
            return self._extract_text(response.content)
        except Exception as e:
            print(f"[LLMSummarizer] summarize failed: {e}")
            return ""

    def merge_summaries(self, summaries: List[str]) -> str:
        """合并多条摘要

        Args:
            summaries: 摘要列表

        Returns:
            合并后的摘要
        """
        llm = self._get_llm()
        if not llm or not summaries:
            return "\n".join(summaries)

        if len(summaries) == 1:
            return summaries[0]

        summaries_text = "\n\n---\n\n".join(
            f"摘要{i+1}: {s}" for i, s in enumerate(summaries)
        )
        prompt = self.MERGE_PROMPT.format(summaries=summaries_text)

        try:
            from langchain_core.messages import HumanMessage
            response = llm.invoke([HumanMessage(content=prompt)])
            return self._extract_text(response.content)
        except Exception as e:
            print(f"[LLMSummarizer] merge failed: {e}")
            return "\n".join(summaries)

    @staticmethod
    def _extract_text(content) -> str:
        """从 LLM 响应中提取文本"""
        if isinstance(content, str):
            return content.strip()
        elif isinstance(content, list):
            if content:
                first = content[0]
                if isinstance(first, dict):
                    return first.get("text", "").strip()
                return getattr(first, "text", "").strip()
        elif isinstance(content, dict):
            return content.get("text", "").strip()
        return str(content).strip()


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
        use_llm_summarizer: bool = False,
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
            use_llm_summarizer: 是否使用 LLM 生成语义摘要（默认 False，使用模板摘要）
        """
        self.messages: List[ChatMessage] = []
        self.max_turns = max_turns
        self.compression_threshold = compression_threshold
        self.use_summarization = use_summarization
        self.summarizer_fn = summarizer_fn
        self.token_budget = token_budget
        self.max_summary_history = max_summary_history
        self.compression_callback = compression_callback
        self.use_llm_summarizer = use_llm_summarizer

        # LLM 摘要生成器（延迟加载）
        self._llm_summarizer: Optional[LLMSummarizer] = None

        # 摘要历史 - 存储被压缩的旧消息摘要
        self._summary_history: List[MessageSummary] = []

        # 压缩统计
        self.compression_count: int = 0
        self.compressed_tokens: int = 0
        self.original_message_count: int = 0

        # 压缩质量跟踪
        self._last_compression_quality: float = 0.0

    def _get_llm_summarizer(self) -> Optional[LLMSummarizer]:
        """延迟加载 LLM 摘要生成器"""
        if self._llm_summarizer is None and self.use_llm_summarizer:
            self._llm_summarizer = LLMSummarizer()
        return self._llm_summarizer

    def _should_compress(self) -> bool:
        """检查是否应该压缩

        触发条件（满足任一即可）：
        1. Token 预算超限：当前消息总 token 超过 token_budget * 0.7（70%预警，100%触发）
        2. 消息数量超限：消息数超过 max_turns * 2 + compression_threshold

        Returns:
            是否应该触发压缩
        """
        # 只在一轮对话结束后检查（消息数为偶数）
        if len(self.messages) % 2 != 0:
            return False

        # 检查消息数量
        max_messages = self.max_turns * 2 + self.compression_threshold
        if len(self.messages) <= max_messages:
            return False

        # 检查是否有足够的旧消息值得压缩（至少2条）
        compressible = len(self.messages) - (self.max_turns * 2)
        if compressible < 2:
            return False

        # 检查 token 预算（使用更激进的 70% 阈值提前压缩）
        total_text = "\n".join(m.content for m in self.messages)
        total_tokens = estimate_tokens(total_text)
        threshold = self.token_budget * 0.7

        return total_tokens > threshold

    def should_compress_warning(self) -> Tuple[bool, float]:
        """检查是否即将达到压缩阈值（用于预警）

        Returns:
            (should_warn, usage_ratio) - 是否应该预警，以及当前使用率
        """
        if len(self.messages) % 2 != 0:
            return False, 0.0

        total_text = "\n".join(m.content for m in self.messages)
        total_tokens = estimate_tokens(total_text)
        usage_ratio = total_tokens / self.token_budget

        # 超过 50% 时预警
        return usage_ratio > 0.5, usage_ratio

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
        # 保留 20% 空间给摘要，60% 给最近消息，20% 作为缓冲
        recent_budget = int(self.token_budget * 0.6)

        # 如果消息数未超限，直接返回
        if len(self.messages) < recent_count:
            return self.messages, ""

        # 估算被压缩内容的 token 数（用于质量评估）
        old_messages_total_tokens = 0

        if incremental:
            # 增量压缩：只压缩超出 budget 的部分
            retained_messages = []
            retained_tokens = 0

            # 从最新消息开始，优先保留
            for msg in reversed(self.messages):
                msg_tokens = estimate_tokens(msg.content)
                if retained_tokens + msg_tokens <= recent_budget:
                    retained_messages.insert(0, msg)
                    retained_tokens += msg_tokens
                elif retained_tokens == 0:
                    # 第一条消息就超出预算，强制截断保留
                    truncated = self._truncate_text_by_token(msg.content, recent_budget)
                    if truncated:
                        retained_messages.insert(0, ChatMessage(role=msg.role, content=truncated))
                        retained_tokens = estimate_tokens(truncated)
                # else: 消息太长且已有一些保留的消息，跳过这条，继续尝试更早的消息

            # 边界情况：如果最终没有保留任何消息，保留最后一条
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

        # 计算被压缩内容的 token 数（用于质量评估）
        old_messages_total_tokens = sum(estimate_tokens(m.content) for m in old_messages)

        # 生成摘要：优先使用自定义函数，其次 LLM，最后模板
        if self.summarizer_fn:
            summary_text = self.summarizer_fn(old_messages)
        elif self.use_llm_summarizer:
            llm_summarizer = self._get_llm_summarizer()
            if llm_summarizer:
                summary_text = llm_summarizer.summarize(old_messages)
            else:
                summary_text = self._default_summarize(old_messages)
        else:
            summary_text = self._default_summarize(old_messages)

        # 计算压缩质量：摘要 token / 原始 token，值越低说明压缩率越高
        if old_messages_total_tokens > 0 and summary_text:
            summary_tokens = estimate_tokens(summary_text)
            self._last_compression_quality = summary_tokens / old_messages_total_tokens
        else:
            self._last_compression_quality = 0.0

        return retained_messages, summary_text

    def _default_summarize(self, messages: List[ChatMessage]) -> str:
        """默认摘要生成（模板方式，不依赖 LLM）

        改进：按 Q&A 对组织，保留语义完整性，token-aware 截断
        """
        if not messages:
            return ""

        # 按 Q&A 对组织消息
        pairs = []
        i = 0
        while i < len(messages):
            if messages[i].role == "user":
                user_msg = messages[i].content
                assistant_msg = ""
                if i + 1 < len(messages) and messages[i + 1].role == "assistant":
                    assistant_msg = messages[i + 1].content
                    i += 2
                else:
                    i += 1
                pairs.append((user_msg, assistant_msg))
            else:
                # 孤立的 assistant 消息
                pairs.append(("", messages[i].content))
                i += 1

        if not pairs:
            return ""

        # Token 预算：摘要总长度不超过 token_budget 的 30%
        summary_budget = int(self.token_budget * 0.3)
        # 每个 Q&A 对的预算
        per_pair_budget = max(80, summary_budget // max(len(pairs), 1))

        summary_parts = [f"共{len(pairs)}轮对话"]

        for idx, (q, a) in enumerate(pairs):
            # 截断问题和回答
            q_snippet = self._truncate_text_by_token(q, per_pair_budget // 2)
            a_snippet = self._truncate_text_by_token(a, per_pair_budget // 2) if a else ""

            pair_text = f"Q: {q_snippet}"
            if a_snippet:
                pair_text += f" → A: {a_snippet}"

            # 检查总预算
            candidate = "；".join(summary_parts + [pair_text])
            if estimate_tokens(candidate) > summary_budget:
                summary_parts.append(f"...还有{len(pairs) - idx}轮")
                break
            summary_parts.append(pair_text)

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

        优先级：最近消息 > 历史摘要
        1. 先放入最近消息（从最新到最旧），保证当前上下文完整
        2. 剩余预算用历史摘要填充
        3. 摘要放在消息前面，保持时间顺序

        Returns:
            格式化的历史字符串，格式：
            用户: xxx
            助手: xxx
            用户: xxx
        """
        if not self.messages and not self._summary_history:
            return "（无历史对话）"

        budget = self.token_budget * 0.8

        # ===== 第一步：收集最近消息（从最新到最旧） =====
        msg_parts = []
        msg_tokens = 0

        for msg in reversed(self.messages):
            role_cn = "用户" if msg.role == "user" else "助手"
            msg_text = f"{role_cn}: {msg.content}"
            t = estimate_tokens(msg_text)
            if msg_tokens + t <= budget:
                msg_parts.insert(0, msg_text)
                msg_tokens += t
            else:
                break

        # ===== 第二步：剩余预算填充摘要 =====
        summary_parts = []
        summary_tokens = 0
        remaining = budget - msg_tokens

        if self.use_summarization and self._summary_history and remaining > 0:
            for s in reversed(self._summary_history):
                part = "【对话摘要】" + s.content
                t = estimate_tokens(part)
                if summary_tokens + t <= remaining:
                    summary_parts.insert(0, part)
                    summary_tokens += t
                elif summary_tokens == 0:
                    truncated = self._truncate_text_by_token(part, remaining)
                    if truncated:
                        summary_parts.insert(0, truncated)
                    break
                else:
                    break

        # ===== 第三步：拼接（摘要在前，消息在后） =====
        result_parts = summary_parts + msg_parts
        return "\n".join(result_parts) if result_parts else "（无历史对话）"

    def get_history_for_rag(self) -> str:
        """获取适合 RAG 使用的对话历史

        优先级：最近消息 > 历史摘要
        1. 先放入最近消息（从最新到最旧），保证当前上下文完整
        2. 剩余预算用历史摘要填充
        3. 摘要放在消息前面，保持时间顺序
        """
        if not self.messages and not self._summary_history:
            return ""

        # 使用 60% 预算给最近消息，20% 给摘要，20% 缓冲
        msg_budget = int(self.token_budget * 0.6)

        # ===== 第一步：收集最近消息（从最新到最旧） =====
        recent_messages = self.messages[-(self.max_turns * 2):]
        msg_parts = []
        msg_tokens = 0

        for msg in reversed(recent_messages):
            role_cn = "用户" if msg.role == "user" else "助手"
            msg_text = role_cn + ": " + msg.content
            t = estimate_tokens(msg_text)
            if msg_tokens + t <= msg_budget:
                msg_parts.insert(0, msg_text)
                msg_tokens += t
            elif msg_tokens == 0:
                # 第一条消息就超预算，截断保留
                truncated = self._truncate_text_by_token(msg.content, msg_budget)
                if truncated:
                    msg_parts.insert(0, role_cn + ": " + truncated)
                    msg_tokens = estimate_tokens(msg_parts[0])
            # else: 超预算且已有保留消息，跳过

        # ===== 第二步：剩余预算填充摘要 =====
        summary_parts = []
        summary_tokens = 0
        remaining = self.token_budget - msg_tokens

        if self.use_summarization and self._summary_history and remaining > 0:
            # 从最新摘要到最旧，优先保留最近的摘要
            for s in reversed(self._summary_history):
                part = "【历史摘要】" + s.content
                t = estimate_tokens(part)
                if summary_tokens + t <= remaining:
                    summary_parts.insert(0, part)
                    summary_tokens += t
                elif summary_tokens == 0:
                    # 第一条摘要就超预算，截断它
                    truncated = self._truncate_text_by_token(part, remaining)
                    if truncated:
                        summary_parts.insert(0, truncated)
                        summary_tokens = estimate_tokens(truncated)
                    break
                else:
                    break

        # ===== 第三步：拼接（摘要在前，消息在后） =====
        result_parts = summary_parts + msg_parts
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

            # 摘要历史过多时，合并旧摘要而非直接丢弃
            self._merge_old_summaries()

        # 保留消息
        self.messages = retained_messages

        # 调用压缩回调
        if self.compression_callback:
            self.compression_callback.on_compress(self.get_compression_stats())

        # 只有实际发生了压缩才返回 True
        return bool(old_messages and summary_content)

    def _merge_old_summaries(self):
        """合并旧摘要，而非 FIFO 丢弃

        当摘要数量超过 max_summary_history 时，将最旧的一半摘要合并成一条。
        """
        if len(self._summary_history) <= self.max_summary_history:
            return

        # 计算需要合并的数量：合并最旧的一半
        merge_count = len(self._summary_history) - self.max_summary_history + 1
        if merge_count < 2:
            merge_count = 2

        # 取出要合并的旧摘要
        old_summaries = self._summary_history[:merge_count]
        remaining = self._summary_history[merge_count:]

        # 合并摘要内容
        summary_texts = [s.content for s in old_summaries]

        # 优先使用 LLM 合并
        llm_summarizer = self._get_llm_summarizer()
        if llm_summarizer:
            merged_content = llm_summarizer.merge_summaries(summary_texts)
        else:
            # 回退：简单拼接
            merged_content = " | ".join(summary_texts)

        # 截断过长的合并结果（使用 token 预算，保持一致性）
        merged_budget = int(self.token_budget * 0.25)  # 合并后摘要不超过 25% token 预算
        if estimate_tokens(merged_content) > merged_budget:
            merged_content = self._truncate_text_by_token(merged_content, merged_budget)

        # 创建合并后的摘要
        merged_summary = MessageSummary(
            content=merged_content,
            original_count=sum(s.original_count for s in old_summaries),
            first_msg_time=old_summaries[0].first_msg_time,
            last_msg_time=old_summaries[-1].last_msg_time,
        )

        # 替换旧摘要
        self._summary_history = [merged_summary] + remaining

    def clear(self, clear_stats: bool = False) -> None:
        """清空对话历史

        Args:
            clear_stats: 是否同时清除压缩统计
        """
        self.messages = []
        self._summary_history = []
        self._last_compression_quality = 0.0
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
        # 计算当前 token 使用情况
        total_text = "\n".join(m.content for m in self.messages)
        current_tokens = estimate_tokens(total_text)
        usage_ratio = current_tokens / self.token_budget if self.token_budget > 0 else 0

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
            "current_tokens": current_tokens,
            "token_budget": self.token_budget,
            "token_usage_ratio": f"{usage_ratio * 100:.1f}%",
            "last_compression_quality": (
                f"{self._last_compression_quality * 100:.1f}%"
                if self._last_compression_quality > 0 else "N/A"
            ),
        }

    def get_compression_quality(self) -> float:
        """获取最近一次压缩的质量指标

        Returns:
            压缩质量比率（摘要token/原始token），越低说明压缩效果越好
        """
        return self._last_compression_quality

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
        use_llm_summarizer: bool = False,
    ):
        self.memory = ConversationMemory(
            max_turns=max_turns,
            compression_threshold=compression_threshold,
            use_summarization=use_summarization,
            max_summary_history=max_summary_history,
            compression_callback=compression_callback,
            use_llm_summarizer=use_llm_summarizer,
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
