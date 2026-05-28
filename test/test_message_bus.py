"""测试消息总线"""
import pytest
import asyncio
from kgsrc.knowledge_vector.multi_agent.message_bus import MessageBus, get_message_bus
from kgsrc.knowledge_vector.multi_agent.types import MessageType


@pytest.fixture
def message_bus():
    return MessageBus()


@pytest.mark.asyncio
class TestMessageBus:
    """测试 MessageBus"""

    async def test_send_message(self, message_bus):
        await message_bus.start()
        msg = await message_bus.send_message(
            msg_type=MessageType.TASK_ASSIGNMENT,
            from_agent="orchestrator",
            to_agent="worker-1",
            content={"task_id": "task-1"},
            task_id="task-1"
        )
        assert msg.id is not None
        assert msg.type == MessageType.TASK_ASSIGNMENT
        await message_bus.stop()

    async def test_broadcast(self, message_bus):
        await message_bus.start()
        received = []

        async def handler(msg):
            received.append(msg)

        await message_bus.subscribe("worker-*", handler)

        await message_bus.broadcast(
            msg_type=MessageType.STATUS_UPDATE,
            from_agent="orchestrator",
            content={"status": "running"},
            task_id="task-1"
        )

        # 等待消息处理
        await asyncio.sleep(0.1)
        assert len(received) == 1
        await message_bus.stop()

    async def test_subscribe_unsubscribe(self, message_bus):
        await message_bus.start()
        call_count = []

        async def handler(msg):
            call_count.append(msg)

        await message_bus.subscribe("worker-1", handler)
        await message_bus.send_message(
            MessageType.TASK_ASSIGNMENT,
            from_agent="orchestrator",
            to_agent="worker-1",
            content={}
        )

        await asyncio.sleep(0.1)
        assert len(call_count) == 1

        await message_bus.unsubscribe("worker-1", handler)
        await message_bus.send_message(
            MessageType.TASK_ASSIGNMENT,
            from_agent="orchestrator",
            to_agent="worker-1",
            content={}
        )

        await asyncio.sleep(0.1)
        assert len(call_count) == 1  # 不再增加
        await message_bus.stop()
