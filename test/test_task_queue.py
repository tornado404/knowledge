"""测试任务队列"""
import pytest
import asyncio
from kgsrc.knowledge_vector.multi_agent.task_queue import TaskQueue, get_task_queue
from kgsrc.knowledge_vector.multi_agent.types import (
    Subtask, SubtaskType, TaskStatus
)


@pytest.fixture
def task_queue():
    return TaskQueue(max_subtasks=5)


@pytest.mark.asyncio
class TestTaskQueue:
    """测试 TaskQueue"""

    async def test_create_task(self, task_queue):
        state = await task_queue.create_task(
            session_id="sess-1",
            question="测试问题"
        )
        assert state.session_id == "sess-1"
        assert state.task_id is not None
        assert state.status == TaskStatus.PENDING

    async def test_get_task(self, task_queue):
        state = await task_queue.create_task(
            session_id="sess-1",
            question="测试问题"
        )
        retrieved = await task_queue.get_task(state.task_id)
        assert retrieved is not None
        assert retrieved.task_id == state.task_id

    async def test_add_subtask(self, task_queue):
        state = await task_queue.create_task(
            session_id="sess-1",
            question="测试"
        )
        subtask = Subtask(
            id="sub-1",
            type=SubtaskType.RAG_RETRIEVE,
            description="检索知识库"
        )
        result = await task_queue.add_subtask(state.task_id, subtask)
        assert result is True

        task = await task_queue.get_task(state.task_id)
        assert len(task.subtasks) == 1

    async def test_update_subtask_status(self, task_queue):
        state = await task_queue.create_task(
            session_id="sess-1",
            question="测试"
        )
        subtask = Subtask(
            id="sub-1",
            type=SubtaskType.RAG_RETRIEVE,
            description="检索"
        )
        await task_queue.add_subtask(state.task_id, subtask)

        await task_queue.update_subtask_status(
            state.task_id, "sub-1", TaskStatus.DONE, "结果"
        )

        task = await task_queue.get_task(state.task_id)
        assert task.subtasks[0].status == TaskStatus.DONE
        assert task.subtasks[0].result == "结果"

    async def test_get_ready_subtasks(self, task_queue):
        state = await task_queue.create_task(
            session_id="sess-1",
            question="测试"
        )
        subtask1 = Subtask(
            id="sub-1",
            type=SubtaskType.RAG_RETRIEVE,
            description="检索"
        )
        subtask2 = Subtask(
            id="sub-2",
            type=SubtaskType.CODE_EXEC,
            description="执行",
            depends_on=["sub-1"]
        )
        await task_queue.add_subtask(state.task_id, subtask1)
        await task_queue.add_subtask(state.task_id, subtask2)

        # 初始只有 subtask1 就绪
        ready = await task_queue.get_ready_subtasks(state.task_id)
        assert len(ready) == 1
        assert ready[0].id == "sub-1"

        # subtask1 完成后，subtask2 就绪
        await task_queue.update_subtask_status(
            state.task_id, "sub-1", TaskStatus.DONE
        )
        ready = await task_queue.get_ready_subtasks(state.task_id)
        assert len(ready) == 1
        assert ready[0].id == "sub-2"

    async def test_is_task_complete(self, task_queue):
        state = await task_queue.create_task(
            session_id="sess-1",
            question="测试"
        )
        subtask1 = Subtask(id="sub-1", type=SubtaskType.RAG_RETRIEVE, description="1")
        subtask2 = Subtask(id="sub-2", type=SubtaskType.WEB_SEARCH, description="2")
        await task_queue.add_subtask(state.task_id, subtask1)
        await task_queue.add_subtask(state.task_id, subtask2)

        # 未完成
        assert await task_queue.is_task_complete(state.task_id) is False

        # 全部完成
        await task_queue.update_subtask_status(state.task_id, "sub-1", TaskStatus.DONE)
        await task_queue.update_subtask_status(state.task_id, "sub-2", TaskStatus.DONE)
        assert await task_queue.is_task_complete(state.task_id) is True

    async def test_set_pending_feedback(self, task_queue):
        state = await task_queue.create_task(
            session_id="sess-1",
            question="测试"
        )
        await task_queue.set_pending_feedback(
            state.task_id,
            {"question": "确认执行?", "options": ["是", "否"]}
        )

        task = await task_queue.get_task(state.task_id)
        assert task.pending_feedback is not None
        assert task.status == TaskStatus.PAUSED

    async def test_max_subtasks_limit(self, task_queue):
        state = await task_queue.create_task(
            session_id="sess-1",
            question="测试"
        )
        # 尝试添加 6 个子任务（限制为5）
        for i in range(6):
            subtask = Subtask(id=f"sub-{i}", type=SubtaskType.RAG_RETRIEVE, description=f"{i}")
            result = await task_queue.add_subtask(state.task_id, subtask)

        task = await task_queue.get_task(state.task_id)
        assert len(task.subtasks) == 5
