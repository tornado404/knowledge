"""Agent 间消息传递系统"""
import asyncio
import uuid
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime

from .types import AgentMessage, MessageType


class MessageBus:
    """消息总线 - Agent 间通信中枢"""

    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._message_queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        self._processor_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    async def start(self):
        """启动消息处理器"""
        if self._running:
            return
        self._running = True
        self._processor_task = asyncio.create_task(self._process_messages())

    async def stop(self):
        """停止消息处理器"""
        self._running = False
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass

    async def subscribe(self, agent_id: str, callback: Callable):
        """订阅消息"""
        async with self._lock:
            if agent_id not in self._subscribers:
                self._subscribers[agent_id] = []
            self._subscribers[agent_id].append(callback)

    async def unsubscribe(self, agent_id: str, callback: Callable):
        """取消订阅"""
        async with self._lock:
            if agent_id in self._subscribers:
                self._subscribers[agent_id] = [
                    cb for cb in self._subscribers[agent_id]
                    if cb != callback
                ]

    async def send_message(
        self,
        msg_type: MessageType,
        from_agent: str,
        to_agent: str,
        content: Dict,
        task_id: Optional[str] = None
    ) -> AgentMessage:
        """发送消息"""
        message = AgentMessage(
            id=str(uuid.uuid4()),
            type=msg_type,
            from_agent=from_agent,
            to_agent=to_agent,
            content=content,
            task_id=task_id
        )
        await self._message_queue.put(message)
        return message

    async def broadcast(
        self,
        msg_type: MessageType,
        from_agent: str,
        content: Dict,
        task_id: Optional[str] = None
    ):
        """广播消息给所有订阅者"""
        message = AgentMessage(
            id=str(uuid.uuid4()),
            type=msg_type,
            from_agent=from_agent,
            to_agent="*",
            content=content,
            task_id=task_id
        )
        await self._message_queue.put(message)

    async def _process_messages(self):
        """异步处理消息队列"""
        while self._running:
            try:
                message = await asyncio.wait_for(
                    self._message_queue.get(),
                    timeout=1.0
                )
                await self._dispatch_message(message)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"Error processing message: {e}")

    async def _dispatch_message(self, message: AgentMessage):
        """分发消息到订阅者"""
        async with self._lock:
            subscribers = self._subscribers.get(message.to_agent, [])
            # 也通知广播订阅者
            subscribers.extend(self._subscribers.get("*", []))

        for callback in subscribers:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(message)
                else:
                    callback(message)
            except Exception as e:
                print(f"Error in message callback: {e}")

    async def get_messages_for_agent(
        self,
        agent_id: str,
        limit: int = 50
    ) -> List[AgentMessage]:
        """获取指定 Agent 的消息历史"""
        # 实际应该持久化存储，这里简化处理
        messages = []
        while not self._message_queue.empty():
            try:
                msg = self._message_queue.get_nowait()
                if msg.to_agent == agent_id or msg.to_agent == "*":
                    messages.append(msg)
            except asyncio.QueueEmpty:
                break
        return messages[-limit:]


# 全局消息总线实例
_message_bus: Optional[MessageBus] = None


def get_message_bus() -> MessageBus:
    """获取全局消息总线实例"""
    global _message_bus
    if _message_bus is None:
        _message_bus = MessageBus()
    return _message_bus
