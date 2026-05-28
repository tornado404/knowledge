"""子 Agent 基类"""
import asyncio
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from .types import (
    Subtask, SubtaskType, WorkerState, WorkerStatus, MessageType, AgentType
)
from .message_bus import get_message_bus
from .task_queue import get_task_queue
from .feedback import get_feedback_manager
from .sandbox_pool import get_sandbox_pool
from .tools.base import ToolResult


@dataclass
class WorkerConfig:
    """Worker 配置"""
    agent_id: str
    agent_type: AgentType
    sandbox_enabled: bool = True
    feedback_enabled: bool = True


class BaseWorker(ABC):
    """子 Agent 基类"""

    def __init__(self, config: WorkerConfig):
        self.config = config
        self.state = WorkerState(
            agent_id=config.agent_id,
            agent_type=config.agent_type,
            status=WorkerStatus.IDLE
        )
        self._message_bus = get_message_bus()
        self._task_queue = get_task_queue()
        self._feedback_manager = get_feedback_manager()
        self._sandbox_pool = get_sandbox_pool()
        self._running = False

    async def start(self):
        """启动 Worker"""
        self._running = True
        await self._message_bus.subscribe(
            self.config.agent_id,
            self._handle_message
        )

    async def stop(self):
        """停止 Worker"""
        self._running = False
        await self._message_bus.unsubscribe(
            self.config.agent_id,
            self._handle_message
        )

    async def _handle_message(self, message):
        """处理收到的消息"""
        if message.type == MessageType.TASK_ASSIGNMENT:
            await self._handle_task_assignment(message)
        elif message.type == MessageType.USER_FEEDBACK:
            await self._handle_user_feedback(message)

    async def _handle_task_assignment(self, message):
        """处理任务分配"""
        content = message.content
        subtask = content.get("subtask")
        if not subtask:
            return

        self.state.current_task = Subtask(
            id=subtask["id"],
            type=SubtaskType(subtask["type"]),
            description=subtask["description"]
        )
        self.state.status = WorkerStatus.RUNNING

        try:
            result = await self.execute_task(self.state.current_task)

            # 发送结果给 Orchestrator
            await self._message_bus.send_message(
                msg_type=MessageType.TOOL_RESULT,
                from_agent=self.config.agent_id,
                to_agent="orchestrator",
                content={
                    "subtask_id": self.state.current_task.id,
                    "result": result.output,
                    "success": result.success,
                    "error": result.error
                },
                task_id=message.task_id
            )

        except Exception as e:
            # 请求用户确认
            if self.config.feedback_enabled:
                await self._request_feedback(
                    task_id=message.task_id,
                    question=f"执行出错: {str(e)}",
                    options=["重试", "跳过", "取消"]
                )
            else:
                await self._send_error(message.task_id, str(e))

        finally:
            self.state.status = WorkerStatus.IDLE
            self.state.current_task = None

    async def _handle_user_feedback(self, message):
        """处理用户反馈"""
        content = message.content
        if content.get("agent_id") != self.config.agent_id:
            return

        response = content.get("response")
        if response == "重试" and self.state.current_task:
            self.state.status = WorkerStatus.RUNNING
            try:
                result = await self.execute_task(self.state.current_task)
                await self._send_result(message.task_id, result)
            finally:
                self.state.status = WorkerStatus.IDLE
        elif response == "跳过":
            await self._send_error(message.task_id, "Skipped by user")
        # "取消" 不做任何事，任务失败

    async def _request_feedback(
        self,
        task_id: str,
        question: str,
        options: List[str]
    ):
        """请求用户确认"""
        if not self.state.current_task:
            return

        self.state.status = WorkerStatus.WAITING_FEEDBACK

        feedback_id = await self._feedback_manager.request_feedback(
            task_id=task_id,
            subtask_id=self.state.current_task.id,
            agent_id=self.config.agent_id,
            question=question,
            options=options
        )

        await self._message_bus.send_message(
            msg_type=MessageType.FEEDBACK_REQUEST,
            from_agent=self.config.agent_id,
            to_agent="orchestrator",
            content={
                "feedback_id": feedback_id,
                "question": question,
                "options": options,
                "subtask_id": self.state.current_task.id
            },
            task_id=task_id
        )

    async def _send_result(self, task_id: str, result: ToolResult):
        """发送结果"""
        await self._message_bus.send_message(
            msg_type=MessageType.TOOL_RESULT,
            from_agent=self.config.agent_id,
            to_agent="orchestrator",
            content={
                "subtask_id": self.state.current_task.id if self.state.current_task else None,
                "result": result.output,
                "success": result.success,
                "error": result.error
            },
            task_id=task_id
        )

    async def _send_error(self, task_id: str, error: str):
        """发送错误"""
        await self._message_bus.send_message(
            msg_type=MessageType.TOOL_RESULT,
            from_agent=self.config.agent_id,
            to_agent="orchestrator",
            content={
                "subtask_id": self.state.current_task.id if self.state.current_task else None,
                "result": None,
                "success": False,
                "error": error
            },
            task_id=task_id
        )

    @abstractmethod
    async def execute_task(self, subtask: Subtask) -> ToolResult:
        """执行子任务，子类实现"""
        pass

    def get_state(self) -> WorkerState:
        """获取当前状态"""
        return self.state
