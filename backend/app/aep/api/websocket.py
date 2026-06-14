"""WebSocket endpoints for real-time AEP streams.

Provides live activity feeds and execution log streaming to the
frontend. Falls back gracefully when no WebSocket upgrade is received.
"""
from __future__ import annotations

import json
import time
import uuid
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.aep.observability import aep_logger

router = APIRouter(prefix="/aep/ws", tags=["aep-websocket"])

_logger = aep_logger("aep.api.websocket")


# ─────────────────────────────────────────────────────────────────────────────
# Connection manager
# ─────────────────────────────────────────────────────────────────────────────


class ConnectionManager:
    """Manages active WebSocket connections by channel."""

    def __init__(self) -> None:
        self._connections: dict[str, list[WebSocket]] = {}

    async def connect(self, channel: str, ws: WebSocket) -> None:
        await ws.accept()
        if channel not in self._connections:
            self._connections[channel] = []
        self._connections[channel].append(ws)

    def disconnect(self, channel: str, ws: WebSocket) -> None:
        if channel in self._connections:
            self._connections[channel] = [
                c for c in self._connections[channel] if c is not ws
            ]
            if not self._connections[channel]:
                del self._connections[channel]

    async def broadcast(self, channel: str, data: dict[str, Any]) -> None:
        if channel not in self._connections:
            return
        message = json.dumps(data)
        dead: list[WebSocket] = []
        for conn in self._connections[channel]:
            try:
                await conn.send_text(message)
            except Exception:
                dead.append(conn)
        for conn in dead:
            self.disconnect(channel, conn)

    @property
    def active_count(self) -> int:
        return sum(len(conns) for conns in self._connections.values())


_manager = ConnectionManager()


def get_connection_manager() -> ConnectionManager:
    """Return the singleton connection manager."""
    return _manager


# ─────────────────────────────────────────────────────────────────────────────
# Activity feed WebSocket
# ─────────────────────────────────────────────────────────────────────────────


@router.websocket("/activity")
async def activity_feed(ws: WebSocket) -> None:
    """Live activity feed for agent invocations and state changes.

    Clients connect here to receive real-time events for the AEP
    agent activity feed page.
    """
    channel = "activity"
    await _manager.connect(channel, ws)
    _logger.info("ws_connected", channel=channel, total=_manager.active_count)
    try:
        while True:
            # Keep connection alive; respond to pings
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_text(json.dumps({"type": "pong", "ts": time.time()}))
    except WebSocketDisconnect:
        pass
    finally:
        _manager.disconnect(channel, ws)
        _logger.info("ws_disconnected", channel=channel, total=_manager.active_count)


# ─────────────────────────────────────────────────────────────────────────────
# Execution log WebSocket
# ─────────────────────────────────────────────────────────────────────────────


@router.websocket("/logs/{execution_id}")
async def execution_logs(ws: WebSocket, execution_id: str) -> None:
    """Stream execution logs in real-time for a specific execution."""
    channel = f"logs:{execution_id}"
    await _manager.connect(channel, ws)
    _logger.info("ws_log_connected", execution_id=execution_id)
    try:
        while True:
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_text(json.dumps({"type": "pong", "ts": time.time()}))
    except WebSocketDisconnect:
        pass
    finally:
        _manager.disconnect(channel, ws)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers for broadcasting from other modules
# ─────────────────────────────────────────────────────────────────────────────


async def emit_activity_event(
    event_type: str,
    agent_name: str,
    execution_id: str | None = None,
    **fields: Any,
) -> None:
    """Broadcast an activity event to all connected activity feed clients."""
    event = {
        "id": str(uuid.uuid4()),
        "timestamp": time.time(),
        "event_type": event_type,
        "agent_name": agent_name,
        "execution_id": execution_id,
        **fields,
    }
    await _manager.broadcast("activity", event)


async def emit_log_entry(
    execution_id: str,
    level: str,
    agent: str,
    message: str,
    **metadata: Any,
) -> None:
    """Broadcast a log entry to clients watching a specific execution."""
    entry = {
        "id": str(uuid.uuid4()),
        "timestamp": time.time(),
        "level": level,
        "agent": agent,
        "message": message,
        "metadata": metadata,
    }
    await _manager.broadcast(f"logs:{execution_id}", entry)
