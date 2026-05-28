"""Multi-Agent API 端点"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from .task_queue import get_task_queue
from .feedback import get_feedback_manager
from .message_bus import get_message_bus
from .types import MessageType

router = APIRouter(prefix="/tasks", tags=["multi-agent"])


class FeedbackRequest(BaseModel):
    """反馈请求模型"""
    response: str
    user_data: Optional[Dict[str, Any]] = None


class TaskStatusResponse(BaseModel):
    """任务状态响应"""
    task_id: str
    status: str
    total_subtasks: int
    done_subtasks: int
    failed_subtasks: int
    pending_feedback: Optional[Dict[str, Any]] = None


@router.get("/{task_id}/status", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """获取任务状态"""
    task_queue = get_task_queue()
    task = await task_queue.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    summary = await task_queue.get_task_summary(task_id)

    return TaskStatusResponse(
        task_id=task_id,
        status=task.status.value,
        total_subtasks=summary["total_subtasks"],
        done_subtasks=summary["done_subtasks"],
        failed_subtasks=summary["failed_subtasks"],
        pending_feedback=task.pending_feedback
    )


@router.post("/{task_id}/feedback")
async def submit_feedback(task_id: str, feedback: FeedbackRequest):
    """提交用户反馈"""
    task_queue = get_task_queue()
    task = await task_queue.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if not task.pending_feedback:
        raise HTTPException(status_code=400, detail="No pending feedback for this task")

    feedback_manager = get_feedback_manager()
    success = await feedback_manager.submit_feedback(
        feedback_id=task.pending_feedback["feedback_id"],
        response=feedback.response,
        user_data=feedback.user_data
    )

    if not success:
        raise HTTPException(status_code=500, detail="Failed to submit feedback")

    return {"status": "ok", "message": "Feedback submitted"}


@router.get("/{task_id}/subtasks")
async def get_subtasks(task_id: str):
    """获取子任务列表"""
    task_queue = get_task_queue()
    task = await task_queue.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return {
        "subtasks": [s.to_dict() for s in task.subtasks]
    }


@router.get("/{task_id}/messages")
async def get_task_messages(task_id: str, limit: int = 50):
    """获取任务相关的消息"""
    task_queue = get_task_queue()
    task = await task_queue.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return {
        "messages": task.messages[-limit:]
    }


@router.delete("/{task_id}/cancel")
async def cancel_task(task_id: str):
    """取消任务"""
    task_queue = get_task_queue()
    task = await task_queue.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    await task_queue.set_task_status(task_id, "failed")
    return {"status": "ok", "message": "Task cancelled"}
