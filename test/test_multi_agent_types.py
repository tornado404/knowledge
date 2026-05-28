"""测试 Multi-Agent 类型定义"""
import pytest
from kgsrc.knowledge_vector.multi_agent.types import (
    SubtaskType,
    TaskStatus,
    AgentType,
    MessageType,
    WorkerStatus,
    Subtask,
    AgentMessage,
    OrchestratorState,
    WorkerState,
)


class TestSubtaskType:
    """测试 SubtaskType 枚举"""

    def test_subtask_types_exist(self):
        assert SubtaskType.RAG_RETRIEVE == "rag_retrieve"
        assert SubtaskType.CODE_EXEC == "code_exec"
        assert SubtaskType.WEB_SEARCH == "web_search"
        assert SubtaskType.FILE_OPS == "file_ops"
        assert SubtaskType.BASH == "bash"


class TestTaskStatus:
    """测试 TaskStatus 枚举"""

    def test_task_statuses_exist(self):
        assert TaskStatus.PENDING == "pending"
        assert TaskStatus.READY == "ready"
        assert TaskStatus.RUNNING == "running"
        assert TaskStatus.DONE == "done"
        assert TaskStatus.FAILED == "failed"
        assert TaskStatus.PAUSED == "paused"


class TestSubtask:
    """测试 Subtask 数据类"""

    def test_subtask_creation(self):
        subtask = Subtask(
            id="test-1",
            type=SubtaskType.RAG_RETRIEVE,
            description="检索知识库"
        )
        assert subtask.id == "test-1"
        assert subtask.type == SubtaskType.RAG_RETRIEVE
        assert subtask.status == TaskStatus.PENDING
        assert subtask.result is None

    def test_subtask_to_dict(self):
        subtask = Subtask(
            id="test-1",
            type=SubtaskType.CODE_EXEC,
            description="执行代码"
        )
        d = subtask.to_dict()
        assert d["id"] == "test-1"
        assert d["type"] == "code_exec"
        assert d["status"] == "pending"


class TestAgentMessage:
    """测试 AgentMessage 数据类"""

    def test_message_creation(self):
        msg = AgentMessage(
            id="msg-1",
            type=MessageType.TASK_ASSIGNMENT,
            from_agent="orchestrator",
            to_agent="worker-1",
            content={"task_id": "task-1"}
        )
        assert msg.id == "msg-1"
        assert msg.type == MessageType.TASK_ASSIGNMENT

    def test_message_to_dict(self):
        msg = AgentMessage(
            id="msg-1",
            type=MessageType.FEEDBACK_REQUEST,
            from_agent="worker-1",
            to_agent="orchestrator",
            content={"question": "确认执行?"}
        )
        d = msg.to_dict()
        assert d["type"] == "feedback_request"
        assert d["from_agent"] == "worker-1"


class TestOrchestratorState:
    """测试 OrchestratorState 数据类"""

    def test_state_creation(self):
        state = OrchestratorState(
            session_id="sess-1",
            task_id="task-1",
            original_question="测试问题"
        )
        assert state.session_id == "sess-1"
        assert state.status == TaskStatus.PENDING

    def test_state_with_subtasks(self):
        subtasks = [
            Subtask(id="1", type=SubtaskType.RAG_RETRIEVE, description="检索"),
            Subtask(id="2", type=SubtaskType.WEB_SEARCH, description="搜索"),
        ]
        state = OrchestratorState(
            session_id="sess-1",
            task_id="task-1",
            original_question="测试",
            subtasks=subtasks
        )
        assert len(state.subtasks) == 2
