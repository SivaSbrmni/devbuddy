"""Session event hub — broadcast live events to WebSocket subscribers."""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Any

import structlog

log = structlog.get_logger()


class SessionEventHub:
    """In-memory pub/sub for session events with optional persistence callback."""

    def __init__(self) -> None:
        self._subscribers: dict[uuid.UUID, list[asyncio.Queue]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, session_id: uuid.UUID) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        async with self._lock:
            if session_id not in self._subscribers:
                self._subscribers[session_id] = []
            self._subscribers[session_id].append(queue)
        return queue

    async def unsubscribe(self, session_id: uuid.UUID, queue: asyncio.Queue) -> None:
        async with self._lock:
            if session_id in self._subscribers and queue in self._subscribers[session_id]:
                self._subscribers[session_id].remove(queue)
                if not self._subscribers[session_id]:
                    del self._subscribers[session_id]

    async def publish(self, session_id: uuid.UUID, event: dict[str, Any]) -> None:
        async with self._lock:
            queues = list(self._subscribers.get(session_id, []))
        for queue in queues:
            try:
                queue.put_nowait(event)
            except Exception:
                pass

    @staticmethod
    def format_event(
        session_id: uuid.UUID,
        seq: int,
        event_type: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "type": event_type,
            "session_id": str(session_id),
            "seq": seq,
            "timestamp": int(time.time() * 1000),
            "payload": payload,
        }

    def sse_line(self, event: dict[str, Any]) -> str:
        return f"data: {json.dumps(event)}\n\n"


session_event_hub = SessionEventHub()
