"""Multi-Agent 系统数据类型定义"""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any
from datetime import datetime


class SubtaskType(str, Enum):
    """子任务类型"""
    RAG_RETRIEVE = "rag_retrieve"      # 知识库检索
    CODE_EXEC = "code_exec"            # 代码执行
    WEB_SEARCH = "web_search"          # 网页搜索
    FILE_OPS = "file_ops"             # 文件操作
    BASH = "bash"                     # Bash 命令


class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"       # 待处理
    READY = "ready"          # 就绪
    RUNNING = "running"      # 执行中
    DONE = "done"           # 已完成
    FAILED = "failed"        # 失败
    PAUSED = "paused"       # 暂停等待确认


class AgentType(str, Enum):
    """Agent 类型"""
    ORCHESTRATOR = "orchestrator"    # 主 Agent (任务规划)
    RAG = "rag"                      # 知识检索 Agent
    CODE = "code"                    # 代码执行 Agent
    WEB = "web"                      # 网页搜索 Agent
    FILE_OPS = "file_ops"           # 文件操作 Agent


class MessageType(str, Enum):
    """消息类型"""
    TASK_ASSIGNMENT = "task_assignment"       # 主 Agent → Worker: 分配任务
    TOOL_RESULT = "tool_result"               # Worker → 主 Agent: 工具执行结果
    SANDBOX_RESULT = "sandbox_result"         # Worker → 主 Agent: 沙盒执行结果
    FEEDBACK_REQUEST = "feedback_request"       # Worker → 主 Agent: 请求用户确认
    USER_FEEDBACK = "user_feedback"           # 用户 → 主 Agent → Worker: 用户审批
    STATUS_UPDATE = "status_update"           # Worker → 主 Agent: 状态变更
    AGENT_MESSAGE = "agent_message"           # Agent 间消息传递


class WorkerStatus(str, Enum):
    """Worker Agent 状态"""
    IDLE = "idle"                 # 空闲
    RUNNING = "running"           # 执行中
    WAITING_FEEDBACK = "waiting_feedback"  # 等待用户确认
    DONE = "done"                 # 完成


@dataclass
class Subtask:
    """子任务定义"""
    id: str
    type: SubtaskType
    description: str
    assigned_agent: Optional[str] = None
    depends_on: List[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "description": self.description,
            "assigned_agent": self.assigned_agent,
            "depends_on": self.depends_on,
            "status": self.status.value,
            "result": self.result,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class AgentMessage:
    """Agent 间消息"""
    id: str
    type: MessageType
    from_agent: str
    to_agent: str
    content: Dict[str, Any]
    task_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "content": self.content,
            "task_id": self.task_id,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class OrchestratorState:
    """主 Agent 状态"""
    session_id: str
    task_id: str
    original_question: str
    subtasks: List[Subtask] = field(default_factory=list)
    active_agent_id: Optional[str] = None
    pending_feedback: Optional[Dict[str, Any]] = None
    messages: List[Dict[str, Any]] = field(default_factory=list)
    context: str = ""
    answer: str = ""
    status: TaskStatus = TaskStatus.PENDING

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "task_id": self.task_id,
            "original_question": self.original_question,
            "subtasks": [s.to_dict() for s in self.subtasks],
            "active_agent_id": self.active_agent_id,
            "pending_feedback": self.pending_feedback,
            "messages": self.messages,
            "context": self.context,
            "answer": self.answer,
            "status": self.status.value,
        }


@dataclass
class WorkerState:
    """子 Agent 状态"""
    agent_id: str
    agent_type: AgentType
    current_task: Optional[Subtask] = None
    tools_result: Dict[str, Any] = field(default_factory=dict)
    sandbox_result: Optional[Dict[str, Any]] = None
    status: WorkerStatus = WorkerStatus.IDLE
    context: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type.value,
            "current_task": self.current_task.to_dict() if self.current_task else None,
            "tools_result": self.tools_result,
            "sandbox_result": self.sandbox_result,
            "status": self.status.value,
            "context": self.context,
        }


@dataclass
class FeedbackRequest:
    """用户反馈请求"""
    task_id: str
    subtask_id: str
    agent_id: str
    question: str
    options: List[str] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "subtask_id": self.subtask_id,
            "agent_id": self.agent_id,
            "question": self.question,
            "options": self.options,
            "context": self.context,
            "created_at": self.created_at.isoformat(),
        }
