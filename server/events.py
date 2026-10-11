"""Broadcast hub feeding the single multiplexed SSE endpoint.

The job worker publishes rendered HTML fragments (queue bar, run panel,
progress, log tail) and JSON notifications; every connected browser tab gets
its own asyncio.Queue. Slow consumers drop the oldest events instead of
blocking the worker (the next event re-renders full state anyway).
"""

import asyncio
from typing import Any, Dict, Optional


class EventHub:
    def __init__(self) -> None:
        self._subscribers: Dict[int, asyncio.Queue] = {}
        self._counter = 0

    def subscribe(self) -> asyncio.Queue:
        self._counter += 1
        queue: asyncio.Queue = asyncio.Queue(maxsize=64)
        self._subscribers[self._counter] = queue
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        for key, value in list(self._subscribers.items()):
            if value is queue:
                del self._subscribers[key]
                break

    @property
    def client_count(self) -> int:
        return len(self._subscribers)

    def publish(self, event: str, data: Any) -> None:
        """Fire-and-forget broadcast; `data` is a string (HTML) or dict (JSON)."""
        for queue in list(self._subscribers.values()):
            try:
                queue.put_nowait({"event": event, "data": data})
            except asyncio.QueueFull:
                try:
                    queue.get_nowait()
                    queue.put_nowait({"event": event, "data": data})
                except (asyncio.QueueFull, asyncio.QueueEmpty):
                    pass  # consumer too slow; full-state events will resync it


_hub: Optional[EventHub] = None


def hub() -> EventHub:
    global _hub
    if _hub is None:
        _hub = EventHub()
    return _hub
