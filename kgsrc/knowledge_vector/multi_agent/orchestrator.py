"""Orchestrator Agent - 主 Agent 负责任务规划分解"""
import asyncio
import uuid
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass

from .types import (
    Subtask, SubtaskType, TaskStatus, MessageType,
    OrchestratorState, AgentMessage
)
from .task_queue import get_task_queue, TaskQueue
from .message_bus import get_message_bus, MessageBus
from .worker import BaseWorker, WorkerConfig
from .tools import (
    ToolResult,
    BashTool, LsTool, CatTool, GrepTool, FindTool,
    WebSearchTool, MilvusSearchTool
)
from .types import AgentType
from .sandbox_pool import get_sandbox_pool
from knowledge_vector.config import config


@dataclass
class WorkerRegistry:
    """Worker 注册表"""
    workers: Dict[str, BaseWorker] = None
    task_queue: TaskQueue = None
    message_bus: MessageBus = None

    def __post_init__(self):
        self.workers = {}
        self.task_queue = get_task_queue()
        self.message_bus = get_message_bus()


class OrchestratorAgent:
    """主 Agent - 负责任务规划、分解、协调子 Agent"""

    def __init__(self):
        self.task_queue = get_task_queue()
        self.message_bus = get_message_bus()
        self.registry = WorkerRegistry()
        self._running = False
        self._worker_tasks: List[asyncio.Task] = []

    async def initialize(self):
        """初始化 Orchestrator"""
        await self.message_bus.start()

        # 订阅来自 Worker 的消息
        await self.message_bus.subscribe("orchestrator", self._handle_worker_message)

        # 注册内置 Worker
        await self._register_builtin_workers()

    async def _handle_worker_message(self, message: AgentMessage):
        """处理来自 Worker 的消息"""
        if message.type == MessageType.TOOL_RESULT:
            await self._handle_tool_result(message)
        elif message.type == MessageType.FEEDBACK_REQUEST:
            await self._handle_feedback_request(message)
        elif message.type == MessageType.STATUS_UPDATE:
            await self._handle_status_update(message)

    async def _handle_tool_result(self, message: AgentMessage):
        """处理工具执行结果"""
        content = message.content
        task_id = message.task_id
        subtask_id = content.get("subtask_id")
        result = content.get("result")
        success = content.get("success", False)
        error = content.get("error")

        if not task_id or not subtask_id:
            return

        # 更新子任务状态
        if success:
            await self.task_queue.update_subtask_status(
                task_id, subtask_id, TaskStatus.DONE, result
            )
        else:
            await self.task_queue.update_subtask_status(
                task_id, subtask_id, TaskStatus.FAILED, error or "Unknown error"
            )

        # 更新任务上下文
        task = await self.task_queue.get_task(task_id)
        if task:
            context_parts = [task.context]
            if result:
                context_parts.append(result)
            task.context = "\n\n".join(filter(None, context_parts))

    async def _handle_feedback_request(self, message: AgentMessage):
        """处理用户反馈请求"""
        content = message.content
        task_id = message.task_id

        if not task_id:
            return

        await self.task_queue.set_pending_feedback(task_id, content)

    async def _handle_status_update(self, message: AgentMessage):
        """处理状态更新"""
        # 可以记录日志或更新内部状态
        pass

    async def _register_builtin_workers(self):
        """注册内置 Worker"""
        # RAG Worker
        self.registry.workers["worker_rag"] = await self._create_worker(
            "worker_rag", AgentType.RAG
        )
        # Web Worker
        self.registry.workers["worker_web"] = await self._create_worker(
            "worker_web", AgentType.WEB
        )
        # FileOps Worker
        self.registry.workers["worker_file"] = await self._create_worker(
            "worker_file", AgentType.FILE_OPS
        )
        # Code Worker
        self.registry.workers["worker_code"] = await self._create_worker(
            "worker_code", AgentType.CODE
        )

    async def _create_worker(
        self,
        worker_id: str,
        agent_type: AgentType
    ) -> BaseWorker:
        """创建 Worker"""
        from .worker import WorkerConfig

        config = WorkerConfig(
            agent_id=worker_id,
            agent_type=agent_type,
            sandbox_enabled=config.multi_agent_enabled,
            feedback_enabled=True
        )

        if agent_type == AgentType.RAG:
            worker = RAGWorker(config)
        elif agent_type == AgentType.WEB:
            worker = WebWorker(config)
        elif agent_type == AgentType.FILE_OPS:
            worker = FileOpsWorker(config)
        elif agent_type == AgentType.CODE:
            worker = CodeWorker(config)
        else:
            worker = GenericWorker(config)

        await worker.start()
        return worker

    async def process_question(
        self,
        session_id: str,
        question: str
    ) -> OrchestratorState:
        """处理用户问题 - 主入口"""
        # 创建任务
        state = await self.task_queue.create_task(
            session_id=session_id,
            question=question
        )

        # 任务规划分解
        subtasks = await self._plan_subtasks(question)
        for subtask in subtasks:
            await self.task_queue.add_subtask(state.task_id, subtask)

        # 启动处理循环
        asyncio.create_task(self._process_task_loop(state.task_id))

        return state

    async def _plan_subtasks(self, question: str) -> List[Subtask]:
        """使用 LLM 分解任务为子任务"""
        # 简单的基于规则的分解
        # 实际应该调用 LLM 进行更智能的分解
        subtasks = []
        task_id = str(uuid.uuid4())[:8]

        question_lower = question.lower()

        # 检查是否需要知识库检索
        if any(kw in question_lower for kw in ["文档", "知识库", "检索", "查找", "相关"]):
            subtasks.append(Subtask(
                id=f"{task_id}-1",
                type=SubtaskType.RAG_RETRIEVE,
                description=f"从知识库检索与问题相关的内容: {question}"
            ))

        # 检查是否需要网页搜索
        if any(kw in question_lower for kw in ["搜索", "查询", "最新", "今天", "新闻", "天气"]):
            subtasks.append(Subtask(
                id=f"{task_id}-2",
                type=SubtaskType.WEB_SEARCH,
                description=f"搜索网页获取相关信息: {question}"
            ))

        # 检查是否需要文件操作
        if any(kw in question_lower for kw in ["列出", "查看", "读取", "分析", "代码"]):
            subtasks.append(Subtask(
                id=f"{task_id}-3",
                type=SubtaskType.FILE_OPS,
                description=f"分析项目文件结构: {question}"
            ))

        # 检查是否需要执行命令
        if any(kw in question_lower for kw in ["执行", "运行", "创建", "修改", "写"]):
            subtasks.append(Subtask(
                id=f"{task_id}-4",
                type=SubtaskType.CODE_EXEC,
                description=f"执行相应命令: {question}"
            ))

        # 如果没有匹配任何类型，至少做一个 RAG 检索
        if not subtasks:
            subtasks.append(Subtask(
                id=f"{task_id}-1",
                type=SubtaskType.RAG_RETRIEVE,
                description=f"检索知识库: {question}"
            ))

        return subtasks

    async def _process_task_loop(self, task_id: str):
        """任务处理循环"""
        while True:
            task = await self.task_queue.get_task(task_id)
            if not task:
                break

            # 检查是否全部完成
            if await self.task_queue.is_task_complete(task_id):
                await self.task_queue.set_task_status(task_id, TaskStatus.DONE)
                await self._generate_final_answer(task_id)
                break

            # 检查是否暂停
            if task.status == TaskStatus.PAUSED:
                await asyncio.sleep(1)
                continue

            # 获取就绪的子任务并分配
            ready_tasks = await self.task_queue.get_ready_subtasks(task_id)
            for subtask in ready_tasks:
                await self._dispatch_subtask(task_id, subtask)

            await asyncio.sleep(0.5)

    async def _dispatch_subtask(self, task_id: str, subtask: Subtask):
        """分发子任务到合适的 Worker"""
        # 根据子任务类型选择 Worker
        worker_map = {
            SubtaskType.RAG_RETRIEVE: "worker_rag",
            SubtaskType.WEB_SEARCH: "worker_web",
            SubtaskType.FILE_OPS: "worker_file",
            SubtaskType.CODE_EXEC: "worker_code",
            SubtaskType.BASH: "worker_code",
        }

        worker_id = worker_map.get(subtask.type, "worker_rag")
        worker = self.registry.workers.get(worker_id)

        if not worker:
            await self.task_queue.update_subtask_status(
                task_id, subtask.id, TaskStatus.FAILED, "Worker not available"
            )
            return

        # 更新任务状态
        await self.task_queue.update_subtask_status(
            task_id, subtask.id, TaskStatus.RUNNING
        )

        # 发送任务给 Worker
        await self.message_bus.send_message(
            msg_type=MessageType.TASK_ASSIGNMENT,
            from_agent="orchestrator",
            to_agent=worker_id,
            content={"subtask": subtask.to_dict()},
            task_id=task_id
        )

    async def _generate_final_answer(self, task_id: str):
        """生成最终答案"""
        task = await self.task_queue.get_task(task_id)
        if not task:
            return

        # 合并所有子任务结果
        results = []
        for subtask in task.subtasks:
            if subtask.result:
                results.append(f"[{subtask.type.value}] {subtask.result}")

        task.answer = "\n\n".join(results) if results else "任务完成，无结果"
        task.status = TaskStatus.DONE

    async def get_task_result(self, task_id: str) -> Optional[Dict]:
        """获取任务结果"""
        task = await self.task_queue.get_task(task_id)
        if not task:
            return None

        return {
            "task_id": task.task_id,
            "status": task.status.value,
            "answer": task.answer,
            "subtasks": [s.to_dict() for s in task.subtasks],
            "pending_feedback": task.pending_feedback
        }

    async def shutdown(self):
        """关闭 Orchestrator"""
        self._running = False
        for worker in self.registry.workers.values():
            await worker.stop()
        await self.message_bus.stop()


# 内置 Worker 实现

class RAGWorker(BaseWorker):
    """RAG 检索 Worker"""

    def __init__(self, config):
        super().__init__(config)
        self.milvus_tool = MilvusSearchTool()

    async def execute_task(self, subtask: Subtask) -> ToolResult:
        # 提取查询内容
        description = subtask.description.replace("从知识库检索与问题相关的内容: ", "")
        description = description.replace("检索知识库: ", "")

        return await self.milvus_tool.execute(query=description, top_k=5)


class WebWorker(BaseWorker):
    """网页搜索 Worker"""

    def __init__(self, config):
        super().__init__(config)
        self.websearch_tool = WebSearchTool()

    async def execute_task(self, subtask: Subtask) -> ToolResult:
        description = subtask.description.replace("搜索网页获取相关信息: ", "")
        description = description.replace("搜索: ", "")

        return await self.websearch_tool.execute(query=description, max_results=5)


class FileOpsWorker(BaseWorker):
    """文件操作 Worker"""

    def __init__(self, config):
        super().__init__(config)
        self.ls_tool = LsTool(base_path="/mnt/e/code/knowledge")
        self.grep_tool = GrepTool(base_path="/mnt/e/code/knowledge")
        self.find_tool = FindTool(base_path="/mnt/e/code/knowledge")

    async def execute_task(self, subtask: Subtask) -> ToolResult:
        description = subtask.description

        if "分析项目文件结构" in description:
            # 先 ls 再 grep
            ls_result = await self.ls_tool.execute(path=".")
            if ls_result.success:
                grep_result = await self.grep_tool.execute(
                    pattern="def |class ",
                    path="kgsrc",
                    recursive=True,
                    file_pattern="*.py"
                )
                return ToolResult(
                    success=True,
                    output=f"{ls_result.output}\n\n{grep_result.output}"
                )
            return ls_result

        return ToolResult(success=False, error="Unknown file operation")


class CodeWorker(BaseWorker):
    """代码执行 Worker"""

    def __init__(self, config):
        super().__init__(config)
        self.bash_tool = BashTool()

    async def execute_task(self, subtask: Subtask) -> ToolResult:
        description = subtask.description

        # 如果需要写操作且沙盒启用，使用沙盒
        if self._sandbox_pool and config.e2b_api_key:
            sandbox_id = await self._sandbox_pool.acquire()
            if sandbox_id:
                try:
                    # 简单命令直接执行
                    command = description.replace("执行相应命令: ", "")
                    return await self._sandbox_pool.execute_in_sandbox(
                        sandbox_id, command
                    )
                finally:
                    await self._sandbox_pool.release(sandbox_id)

        # 否则使用本地 bash
        command = description.replace("执行相应命令: ", "")
        return await self.bash_tool.execute(command)


class GenericWorker(BaseWorker):
    """通用 Worker"""

    async def execute_task(self, subtask: Subtask) -> ToolResult:
        return ToolResult(
            success=True,
            output=f"Generic worker handled: {subtask.description}"
        )


# 全局实例
_orchestrator: Optional[OrchestratorAgent] = None


def get_orchestrator() -> OrchestratorAgent:
    """获取全局 Orchestrator 实例"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = OrchestratorAgent()
    return _orchestrator
