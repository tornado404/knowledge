"""任务队列和状态机管理"""
import asyncio
import uuid
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field

from .types import Subtask, SubtaskType, TaskStatus, OrchestratorState


class TaskQueue:
    """任务队列管理器"""

    def __init__(self, max_subtasks: int = 10):
        self.max_subtasks = max_subtasks
        self._tasks: Dict[str, OrchestratorState] = {}
        self._subtask_callbacks: Dict[str, List[Callable]] = {}
        self._lock = asyncio.Lock()

    async def create_task(
        self,
        session_id: str,
        question: str,
        subtasks: Optional[List[Subtask]] = None
    ) -> OrchestratorState:
        """创建新任务"""
        async with self._lock:
            task_id = str(uuid.uuid4())
            state = OrchestratorState(
                session_id=session_id,
                task_id=task_id,
                original_question=question,
                subtasks=subtasks or [],
                status=TaskStatus.PENDING
            )
            self._tasks[task_id] = state
            return state

    async def get_task(self, task_id: str) -> Optional[OrchestratorState]:
        """获取任务状态"""
        return self._tasks.get(task_id)

    async def get_task_by_session(self, session_id: str) -> Optional[OrchestratorState]:
        """根据 session_id 获取最新任务"""
        for task in reversed(list(self._tasks.values())):
            if task.session_id == session_id:
                return task
        return None

    async def add_subtask(self, task_id: str, subtask: Subtask) -> bool:
        """添加子任务"""
        async with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return False
            if len(task.subtasks) >= self.max_subtasks:
                return False
            task.subtasks.append(subtask)
            return True

    async def update_subtask_status(
        self,
        task_id: str,
        subtask_id: str,
        status: TaskStatus,
        result: Optional[str] = None
    ) -> bool:
        """更新子任务状态"""
        async with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return False
            for subtask in task.subtasks:
                if subtask.id == subtask_id:
                    subtask.status = status
                    if result is not None:
                        subtask.result = result
                    return True
            return False

    async def get_ready_subtasks(self, task_id: str) -> List[Subtask]:
        """获取所有就绪的子任务（依赖都已完成）"""
        task = self._tasks.get(task_id)
        if not task:
            return []

        ready = []
        completed_ids = {
            s.id for s in task.subtasks
            if s.status == TaskStatus.DONE
        }

        for subtask in task.subtasks:
            if subtask.status != TaskStatus.PENDING:
                continue
            # 检查依赖是否都已完成
            if all(dep_id in completed_ids for dep_id in subtask.depends_on):
                ready.append(subtask)

        return ready

    async def set_task_status(self, task_id: str, status: TaskStatus) -> bool:
        """设置任务整体状态"""
        async with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return False
            task.status = status
            return True

    async def set_pending_feedback(
        self,
        task_id: str,
        feedback_data: Optional[Dict]
    ) -> bool:
        """设置待用户确认的反馈"""
        async with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return False
            task.pending_feedback = feedback_data
            if feedback_data:
                task.status = TaskStatus.PAUSED
            return True

    async def append_message(
        self,
        task_id: str,
        message: Dict
    ) -> bool:
        """追加消息到任务"""
        async with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return False
            task.messages.append(message)
            return True

    async def update_context(self, task_id: str, context: str) -> bool:
        """更新合并后的上下文"""
        async with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return False
            task.context = context
            return True

    async def is_task_complete(self, task_id: str) -> bool:
        """检查任务是否全部完成"""
        task = self._tasks.get(task_id)
        if not task:
            return False
        return all(s.status == TaskStatus.DONE for s in task.subtasks)

    async def get_task_summary(self, task_id: str) -> Optional[Dict]:
        """获取任务摘要"""
        task = self._tasks.get(task_id)
        if not task:
            return None
        return {
            "task_id": task.task_id,
            "status": task.status.value,
            "total_subtasks": len(task.subtasks),
            "done_subtasks": sum(1 for s in task.subtasks if s.status == TaskStatus.DONE),
            "failed_subtasks": sum(1 for s in task.subtasks if s.status == TaskStatus.FAILED),
            "paused_subtasks": sum(1 for s in task.subtasks if s.status == TaskStatus.PAUSED),
        }


# 全局任务队列实例
_task_queue: Optional[TaskQueue] = None


def get_task_queue() -> TaskQueue:
    """获取全局任务队列实例"""
    global _task_queue
    if _task_queue is None:
        _task_queue = TaskQueue()
    return _task_queue
