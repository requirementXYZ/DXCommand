"""Event bus: fan-out of JSON frames to all connected websockets."""
from __future__ import annotations

import asyncio
import json
from typing import Any


class EventBus:
    def __init__(self) -> None:
        self._queues: set[asyncio.Queue] = set()
        self._last: dict[str, Any] = {}  # last frame per type, replayed to new clients

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=500)
        self._queues.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._queues.discard(q)

    def snapshot(self) -> list[str]:
        """Frames replayed to a newly connected client."""
        return [json.dumps({"type": t, "data": d}) for t, d in self._last.items()]

    def publish(self, type_: str, data: Any, sticky: bool = True) -> None:
        if sticky:
            self._last[type_] = data
        frame = json.dumps({"type": type_, "data": data})
        for q in list(self._queues):
            try:
                q.put_nowait(frame)
            except asyncio.QueueFull:
                # Slow client: drop it; the websocket handler will notice.
                self._queues.discard(q)
