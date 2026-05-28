"""Multi-Agent 集成测试"""
import pytest
import asyncio

from kgsrc.knowledge_vector.multi_agent import (
    get_orchestrator,
    get_task_queue,
    get_message_bus,
    SubtaskType,
)


@pytest.mark.asyncio
class TestMultiAgentIntegration:
    """Multi-Agent 集成测试"""

    async def test_orchestrator_initialization(self):
        """测试 Orchestrator 初始化"""
        orchestrator = get_orchestrator()
        await orchestrator.initialize()

        # 验证 workers 已注册
        assert len(orchestrator.registry.workers) >= 4
        assert "worker_rag" in orchestrator.registry.workers
        assert "worker_web" in orchestrator.registry.workers
        assert "worker_file" in orchestrator.registry.workers
        assert "worker_code" in orchestrator.registry.workers

        await orchestrator.shutdown()

    async def test_task_creation(self):
        """测试任务创建"""
        orchestrator = get_orchestrator()
        await orchestrator.initialize()

        state = await orchestrator.process_question(
            session_id="test-session",
            question="测试问题"
        )

        assert state.task_id is not None
        assert len(state.subtasks) >= 1

        await orchestrator.shutdown()

    async def test_task_planning_rag(self):
        """测试 RAG 任务规划"""
        orchestrator = get_orchestrator()
        await orchestrator.initialize()

        subtasks = await orchestrator._plan_subtasks(
            "查找关于 Agent 的相关文档"
        )

        # 应该规划出 RAG 检索任务
        rag_tasks = [s for s in subtasks if s.type == SubtaskType.RAG_RETRIEVE]
        assert len(rag_tasks) >= 1

        await orchestrator.shutdown()

    async def test_task_planning_web(self):
        """测试 Web 搜索任务规划"""
        orchestrator = get_orchestrator()
        await orchestrator.initialize()

        subtasks = await orchestrator._plan_subtasks(
            "搜索今天的最新新闻"
        )

        # 应该规划出 Web 搜索任务
        web_tasks = [s for s in subtasks if s.type == SubtaskType.WEB_SEARCH]
        assert len(web_tasks) >= 1

        await orchestrator.shutdown()

    async def test_task_planning_file_ops(self):
        """测试文件操作任务规划"""
        orchestrator = get_orchestrator()
        await orchestrator.initialize()

        subtasks = await orchestrator._plan_subtasks(
            "分析项目文件结构"
        )

        # 应该规划出文件操作任务
        file_tasks = [s for s in subtasks if s.type == SubtaskType.FILE_OPS]
        assert len(file_tasks) >= 1

        await orchestrator.shutdown()

    async def test_get_task_result(self):
        """测试获取任务结果"""
        orchestrator = get_orchestrator()
        await orchestrator.initialize()

        state = await orchestrator.process_question(
            session_id="test-session",
            question="测试"
        )

        # 等待一下
        await asyncio.sleep(0.5)

        result = await orchestrator.get_task_result(state.task_id)
        assert result is not None
        assert "task_id" in result
        assert "status" in result

        await orchestrator.shutdown()
