"""Session Persistence - 会话持久化支持

将 ConversationMemory 状态保存到磁盘，支持服务重启后恢复会话。
"""

import json
import os
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from .memory import ConversationMemory, MessageSummary, ChatMessage


class SessionPersistence:
    """会话持久化管理器

    将 session 状态保存为 JSON 文件，支持:
    - 自动保存（每次 add_message 后）
    - 自动加载（get_memory 时检查磁盘）
    - 过期清理（删除过旧的 session）
    """

    def __init__(
        self,
        storage_dir: str = "./sessions",
        auto_save: bool = True,
        max_age_days: int = 30,
    ):
        """初始化持久化管理器

        Args:
            storage_dir: 存储目录路径
            auto_save: 是否自动保存（每次修改后）
            max_age_days: session 最大保留天数
        """
        self.storage_dir = Path(storage_dir)
        self.auto_save = auto_save
        self.max_age_days = max_age_days

        # 确保存储目录存在
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _get_session_path(self, session_id: str) -> Path:
        """获取 session 文件路径"""
        # 清理 session_id 以防止路径遍历
        safe_id = "".join(c for c in session_id if c.isalnum() or c in "-_.")
        return self.storage_dir / f"{safe_id}.json"

    def save_session(self, session_id: str, memory: ConversationMemory) -> bool:
        """保存 session 到磁盘

        Args:
            session_id: session ID
            memory: ConversationMemory 实例

        Returns:
            是否保存成功
        """
        try:
            path = self._get_session_path(session_id)

            # 序列化 memory 状态
            data = {
                "session_id": session_id,
                "saved_at": datetime.now().isoformat(),
                "config": {
                    "max_turns": memory.max_turns,
                    "compression_threshold": memory.compression_threshold,
                    "use_summarization": memory.use_summarization,
                    "token_budget": memory.token_budget,
                    "max_summary_history": memory.max_summary_history,
                },
                "messages": [
                    {
                        "role": msg.role,
                        "content": msg.content,
                        "timestamp": msg.timestamp,
                    }
                    for msg in memory.messages
                ],
                "summary_history": [
                    {
                        "content": s.content,
                        "original_count": s.original_count,
                        "first_msg_time": s.first_msg_time,
                        "last_msg_time": s.last_msg_time,
                    }
                    for s in memory._summary_history
                ],
                "stats": {
                    "compression_count": memory.compression_count,
                    "compressed_tokens": memory.compressed_tokens,
                    "original_message_count": memory.original_message_count,
                },
            }

            # 写入文件（原子写入）
            temp_path = path.with_suffix(".tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            temp_path.replace(path)

            return True

        except Exception as e:
            print(f"[SessionPersistence] Failed to save session {session_id}: {e}")
            return False

    def load_session(self, session_id: str) -> Optional[ConversationMemory]:
        """从磁盘加载 session

        Args:
            session_id: session ID

        Returns:
            ConversationMemory 实例，如果不存在或加载失败则返回 None
        """
        try:
            path = self._get_session_path(session_id)

            if not path.exists():
                return None

            # 检查文件年龄
            mtime = datetime.fromtimestamp(path.stat().st_mtime)
            age_days = (datetime.now() - mtime).days
            if age_days > self.max_age_days:
                # 过期，删除文件
                path.unlink()
                return None

            # 读取并解析
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 重建 ConversationMemory
            config = data.get("config", {})
            memory = ConversationMemory(
                max_turns=config.get("max_turns", 10),
                compression_threshold=config.get("compression_threshold", 5),
                use_summarization=config.get("use_summarization", True),
                token_budget=config.get("token_budget", 3000),
                max_summary_history=config.get("max_summary_history", 10),
            )

            # 恢复消息
            for msg_data in data.get("messages", []):
                msg = ChatMessage(
                    role=msg_data["role"],
                    content=msg_data["content"],
                    timestamp=msg_data.get("timestamp"),
                )
                memory.messages.append(msg)

            # 恢复摘要历史
            for s_data in data.get("summary_history", []):
                summary = MessageSummary(
                    content=s_data["content"],
                    original_count=s_data["original_count"],
                    first_msg_time=s_data["first_msg_time"],
                    last_msg_time=s_data["last_msg_time"],
                )
                memory._summary_history.append(summary)

            # 恢复统计
            stats = data.get("stats", {})
            memory.compression_count = stats.get("compression_count", 0)
            memory.compressed_tokens = stats.get("compressed_tokens", 0)
            memory.original_message_count = stats.get("original_message_count", 0)

            return memory

        except Exception as e:
            print(f"[SessionPersistence] Failed to load session {session_id}: {e}")
            return None

    def delete_session(self, session_id: str) -> bool:
        """删除 session 文件

        Args:
            session_id: session ID

        Returns:
            是否删除成功
        """
        try:
            path = self._get_session_path(session_id)
            if path.exists():
                path.unlink()
            return True
        except Exception as e:
            print(f"[SessionPersistence] Failed to delete session {session_id}: {e}")
            return False

    def list_sessions(self) -> list:
        """列出所有已保存的 session ID

        Returns:
            session ID 列表
        """
        try:
            sessions = []
            for path in self.storage_dir.glob("*.json"):
                session_id = path.stem
                sessions.append(session_id)
            return sessions
        except Exception as e:
            print(f"[SessionPersistence] Failed to list sessions: {e}")
            return []

    def cleanup_expired(self) -> int:
        """清理过期的 session 文件

        Returns:
            删除的 session 数量
        """
        deleted = 0
        try:
            for path in self.storage_dir.glob("*.json"):
                mtime = datetime.fromtimestamp(path.stat().st_mtime)
                age_days = (datetime.now() - mtime).days
                if age_days > self.max_age_days:
                    path.unlink()
                    deleted += 1
        except Exception as e:
            print(f"[SessionPersistence] Failed to cleanup: {e}")
        return deleted
