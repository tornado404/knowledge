"""SSE Event Manager for PKOS Ingest Pipeline.

Provides thread-safe publish/subscribe for task progress events,
bridging synchronous Worker threads to async SSE streams.
"""

import asyncio
import json
import queue
import threading
from typing import AsyncGenerator, Optional


class EventManager:
    """Manages task SSE event push notifications (thread-safe).

    Architecture:
    - publish() is called from the Worker thread, writes to queue.Queue
    - event_stream() runs in the async event loop, uses
      loop.run_in_executor() to bridge synchronous queue.get()
    - threading.Lock protects _subscribers dict for concurrent access

    Lifecycle:
    - subscribe() creates a per-subscriber queue
    - publish() fans out to all subscribers of a task_id
    - When a terminal event (INDEXED/FAILED/DEAD_LETTER) is published,
      the async generator breaks out of the loop
    - unsubscribe() cleans up when the generator exits
    """

    def __init__(self):
        self._subscribers: dict[str, list[queue.Queue]] = {}
        self._lock = threading.Lock()

    def subscribe(self, task_id: str) -> queue.Queue:
        """Subscribe to events for a task.

        Returns a queue.Queue that will receive event dicts.
        Thread-safe.
        """
        q: queue.Queue = queue.Queue()
        with self._lock:
            if task_id not in self._subscribers:
                self._subscribers[task_id] = []
            self._subscribers[task_id].append(q)
        return q

    def publish(self, task_id: str, event: dict):
        """Publish an event to all subscribers of a task.

        Can be safely called from any thread.
        """
        with self._lock:
            subscribers = list(self._subscribers.get(task_id, []))
        for q in subscribers:
            q.put_nowait(event)

    def unsubscribe(self, task_id: str, q: queue.Queue):
        """Remove a subscriber queue for a task.

        Thread-safe.
        """
        with self._lock:
            if task_id in self._subscribers:
                self._subscribers[task_id] = [
                    s for s in self._subscribers[task_id] if s is not q
                ]
                if not self._subscribers[task_id]:
                    del self._subscribers[task_id]

    async def event_stream(self, task_id: str) -> AsyncGenerator[str, None]:
        """Async generator yielding SSE-formatted event strings.

        Uses loop.run_in_executor() to bridge the synchronous
        queue.get() into the async context without blocking the
        event loop.

        Yields "data: <json>\\n\\n" strings suitable for
        FastAPI StreamingResponse with media_type="text/event-stream".

        Stops when a terminal status (INDEXED, FAILED, DEAD_LETTER)
        is received, then cleans up the subscriber.
        """
        loop = asyncio.get_event_loop()
        q = self.subscribe(task_id)
        try:
            while True:
                event = await loop.run_in_executor(None, q.get)
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                if event.get("status") in ("INDEXED", "FAILED", "DEAD_LETTER"):
                    break
        finally:
            self.unsubscribe(task_id, q)
