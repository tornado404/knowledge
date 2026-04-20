"""Conversation Memory - 对话历史管理器"""

from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime


@dataclass
class ChatMessage:
    """单条对话消息"""
    role: str  # "user" or "assistant"
    content: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class ConversationMemory:
    """对话历史管理器"""

    def __init__(self, max_turns: int = 10):
        """初始化对话历史管理器

        Args:
            max_turns: 最大保存的对话轮数（每轮=用户+助手）
        """
        self.messages: List[ChatMessage] = []
        self.max_turns = max_turns

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

    def get_history_text(self) -> str:
        """获取格式化的对话历史文本

        Returns:
            格式化的历史字符串，格式：
            用户: xxx
            助手: xxx
            用户: xxx
        """
        if not self.messages:
            return "（无历史对话）"

        # 只返回最近 max_turns 轮的内容
        recent_messages = self.messages[-(self.max_turns * 2):]
        lines = []
        for msg in recent_messages:
            role_cn = "用户" if msg.role == "user" else "助手"
            lines.append(f"{role_cn}: {msg.content}")

        return "\n".join(lines)

    def get_history_for_rag(self) -> str:
        """获取适合 RAG 使用的对话历史

        与 get_history_text 类似，但格式更简洁
        """
        if not self.messages:
            return ""

        recent_messages = self.messages[-(self.max_turns * 2):]
        lines = []
        for msg in recent_messages:
            role_cn = "用户" if msg.role == "user" else "助手"
            lines.append(f"{role_cn}: {msg.content}")

        return "\n".join(lines)

    def clear(self) -> None:
        """清空对话历史"""
        self.messages = []

    @property
    def turn_count(self) -> int:
        """获取当前对话轮数"""
        return len(self.messages) // 2

    @property
    def is_empty(self) -> bool:
        """检查是否为空"""
        return len(self.messages) == 0

    def get_messages(self) -> List[ChatMessage]:
        """获取所有消息"""
        return self.messages.copy()

    def get_recent_messages(self, n: int) -> List[ChatMessage]:
        """获取最近 n 条消息"""
        return self.messages[-n:] if self.messages else []

    def __len__(self) -> int:
        return len(self.messages)

    def __repr__(self) -> str:
        return f"ConversationMemory(turns={self.turn_count}, messages={len(self.messages)})"
