"""Tests for EventManager — SSE event pub/sub system."""

import time
import queue
import threading
import pytest
from kgsrc.pkos.events import EventManager


def test_event_manager_publish_subscribe():
    """Publish after subscribe — subscriber receives the event."""
    em = EventManager()
    q = em.subscribe("task-1")

    em.publish("task-1", {"stage": "PARSING", "status": "PARSING", "progress": 0.2})

    result = q.get(timeout=1.0)
    assert result["stage"] == "PARSING"
    assert result["status"] == "PARSING"
    assert result["progress"] == 0.2


def test_event_manager_multiple_subscribers():
    """Multiple subscribers to same task_id all receive events."""
    em = EventManager()
    q1 = em.subscribe("task-1")
    q2 = em.subscribe("task-1")

    em.publish("task-1", {"stage": "INDEXED", "status": "INDEXED", "progress": 1.0})

    r1 = q1.get(timeout=1.0)
    r2 = q2.get(timeout=1.0)
    assert r1 == r2 == {"stage": "INDEXED", "status": "INDEXED", "progress": 1.0}


def test_event_manager_unsubscribe():
    """After unsubscribe, subscriber no longer receives events."""
    em = EventManager()
    q = em.subscribe("task-1")
    em.unsubscribe("task-1", q)

    em.publish("task-1", {"stage": "PARSING", "status": "PARSING", "progress": 0.2})

    # Queue should remain empty — no event received
    with pytest.raises(queue.Empty):
        q.get(timeout=0.5)


def test_event_manager_different_task_ids():
    """Events for different task_ids do not cross-pollinate."""
    em = EventManager()
    q1 = em.subscribe("task-a")
    q2 = em.subscribe("task-b")

    em.publish("task-a", {"stage": "INDEXED", "status": "INDEXED", "progress": 1.0})

    r1 = q1.get(timeout=1.0)
    assert r1["status"] == "INDEXED"

    # task-b subscriber should NOT receive task-a's event
    with pytest.raises(queue.Empty):
        q2.get(timeout=0.5)


def test_event_manager_terminal_event_disconnects():
    """After terminal event (INDEXED/FAILED), event_stream stops."""
    em = EventManager()

    async def consume():
        events = []
        async for event in em.event_stream("task-term"):
            events.append(event)
        return events

    import asyncio
    # Start consumer in background
    async def run():
        consumer = asyncio.create_task(consume())
        await asyncio.sleep(0.05)
        em.publish("task-term", {"stage": "COMPLETE", "status": "INDEXED", "progress": 1.0})
        await asyncio.sleep(0.05)
        events = await consumer
        return events

    events = asyncio.run(run())
    assert len(events) == 1
    assert '"status": "INDEXED"' in events[0]


def test_event_manager_thread_safety():
    """Concurrent publish from multiple threads is safe."""
    em = EventManager()
    q = em.subscribe("thread-safe-task")

    def publisher():
        for i in range(50):
            em.publish("thread-safe-task", {"stage": "PARSING", "status": "PARSING", "progress": i / 50})
            time.sleep(0.001)

    t = threading.Thread(target=publisher, daemon=True)
    t.start()

    received = 0
    while received < 50:
        try:
            q.get(timeout=2.0)
            received += 1
        except queue.Empty:
            break

    t.join(timeout=2.0)
    assert received == 50
