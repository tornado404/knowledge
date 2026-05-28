"""用户反馈处理模块"""
import asyncio
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
import uuid

from .types import FeedbackRequest, TaskStatus
from .task_queue import get_task_queue
from .message_bus import get_message_bus, MessageType


class FeedbackManager:
    """用户反馈管理器"""

    def __init__(self):
        self._pending_feedbacks: Dict[str, FeedbackRequest] = {}
        self._callbacks: Dict[str, List[Callable]] = {}
        self._lock = asyncio.Lock()

    async def request_feedback(
        self,
        task_id: str,
        subtask_id: str,
        agent_id: str,
        question: str,
        options: Optional[List[str]] = None,
        context: Optional[Dict] = None
    ) -> str:
        """请求用户反馈，返回 feedback_id"""
        async with self._lock:
            feedback_id = str(uuid.uuid4())
            request = FeedbackRequest(
                task_id=task_id,
                subtask_id=subtask_id,
                agent_id=agent_id,
                question=question,
                options=options or ["确认", "取消"],
                context=context or {}
            )
            self._pending_feedbacks[feedback_id] = request

            # 更新任务状态为 PAUSED
            task_queue = get_task_queue()
            await task_queue.set_pending_feedback(
                task_id,
                {
                    "feedback_id": feedback_id,
                    "question": question,
                    "options": options,
                    "subtask_id": subtask_id,
                    "agent_id": agent_id
                }
            )

            return feedback_id

    async def get_feedback(self, feedback_id: str) -> Optional[FeedbackRequest]:
        """获取反馈请求"""
        return self._pending_feedbacks.get(feedback_id)

    async def submit_feedback(
        self,
        feedback_id: str,
        response: str,
        user_data: Optional[Dict] = None
    ) -> bool:
        """提交用户反馈"""
        async with self._lock:
            request = self._pending_feedbacks.get(feedback_id)
            if not request:
                return False

            # 通知所有等待此反馈的回调
            task_queue = get_task_queue()
            message_bus = get_message_bus()

            # 构造反馈消息
            feedback_msg = {
                "feedback_id": feedback_id,
                "response": response,
                "user_data": user_data,
                "subtask_id": request.subtask_id,
                "agent_id": request.agent_id,
            }

            # 发送反馈给相关 Agent
            await message_bus.send_message(
                msg_type=MessageType.USER_FEEDBACK,
                from_agent="user",
                to_agent=request.agent_id,
                content=feedback_msg,
                task_id=request.task_id
            )

            # 清除待处理反馈
            del self._pending_feedbacks[feedback_id]

            # 恢复任务状态
            await task_queue.set_pending_feedback(request.task_id, None)

            return True

    async def get_pending_for_task(self, task_id: str) -> List[FeedbackRequest]:
        """获取任务的所有待处理反馈"""
        return [
            f for f in self._pending_feedbacks.values()
            if f.task_id == task_id
        ]

    async def register_callback(
        self,
        feedback_id: str,
        callback: Callable
    ):
        """注册反馈回调"""
        if feedback_id not in self._callbacks:
            self._callbacks[feedback_id] = []
        self._callbacks[feedback_id].append(callback)

    async def cancel_feedback(self, feedback_id: str) -> bool:
        """取消反馈请求"""
        async with self._lock:
            if feedback_id in self._pending_feedbacks:
                request = self._pending_feedbacks[feedback_id]
                del self._pending_feedbacks[feedback_id]

                # 恢复任务状态
                task_queue = get_task_queue()
                await task_queue.set_pending_feedback(request.task_id, None)

                return True
        return False


# 全局反馈管理器实例
_feedback_manager: Optional[FeedbackManager] = None


def get_feedback_manager() -> FeedbackManager:
    """获取全局反馈管理器实例"""
    global _feedback_manager
    if _feedback_manager is None:
        _feedback_manager = FeedbackManager()
    return _feedback_manager
