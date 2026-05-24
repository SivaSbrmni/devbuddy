"""
MCP Connections API
====================
CRUD for external MCP / log-source connections.
Supports: Loki, Datadog, CloudWatch, custom HTTP endpoints.
"""
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.logger import get_logger
from app.core.crypto import encrypt_secret, decrypt_secret
from app.models.mcp_connection import McpConnection

router = APIRouter(prefix="/mcp", tags=["mcp"])
logger = get_logger("mcp_connections")


# ── Schemas ─────────────────────────────────────────────────────────────────

class McpConnectionCreate(BaseModel):
    name: str
    description: str = ""
    conn_type: str = "custom_http"   # loki | datadog | cloudwatch | custom_http | custom_mcp
    url: str = ""
    api_key: str = ""
    config: dict[str, Any] = {}
    is_active: bool = True


class McpConnectionUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    url: str | None = None
    api_key: str | None = None
    config: dict[str, Any] | None = None
    is_active: bool | None = None


class McpConnectionOut(BaseModel):
    id: str
    name: str
    description: str
    conn_type: str
    url: str
    has_api_key: bool
    config: dict
    is_active: bool
    last_tested_at: str | None
    last_test_ok: bool | None
    last_test_msg: str | None
    created_at: str

    class Config:
        from_attributes = True


def _to_out(c: McpConnection) -> McpConnectionOut:
    return McpConnectionOut(
        id=str(c.id),
        name=c.name,
        description=c.description or "",
        conn_type=c.conn_type,
        url=c.url or "",
        has_api_key=bool(c.api_key),
        config=c.config or {},
        is_active=c.is_active,
        last_tested_at=c.last_tested_at.isoformat() if c.last_tested_at else None,
        last_test_ok=c.last_test_ok,
        last_test_msg=c.last_test_msg,
        created_at=c.created_at.isoformat(),
    )


# ── Routes ───────────────────────────────────────────────────────────────────

@router.get("/connections")
async def list_connections(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(McpConnection).where(McpConnection.tenant_id == uuid.UUID(user["tenant_id"])).order_by(McpConnection.created_at.desc())
    )
    conns = result.scalars().all()
    return [_to_out(c) for c in conns]


@router.post("/connections", status_code=201)
async def create_connection(
    body: McpConnectionCreate,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conn = McpConnection(
        tenant_id=uuid.UUID(user["tenant_id"]),
        name=body.name,
        description=body.description,
        conn_type=body.conn_type,
        url=body.url,
        api_key=encrypt_secret(body.api_key) if body.api_key else None,
        config=body.config,
        is_active=body.is_active,
    )
    db.add(conn)
    await db.commit()
    await db.refresh(conn)
    logger.info("mcp_connection_created", id=str(conn.id), name=conn.name)
    return _to_out(conn)


@router.patch("/connections/{conn_id}")
async def update_connection(
    conn_id: str,
    body: McpConnectionUpdate,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(McpConnection).where(McpConnection.id == uuid.UUID(conn_id)))
    conn = result.scalar_one_or_none()
    if not conn or str(conn.tenant_id) != user["tenant_id"]:
        raise HTTPException(404, "Not found")
    if body.name is not None:
        conn.name = body.name
    if body.description is not None:
        conn.description = body.description
    if body.url is not None:
        conn.url = body.url
    if body.api_key is not None:
        conn.api_key = encrypt_secret(body.api_key) if body.api_key else None
    if body.config is not None:
        conn.config = body.config
    if body.is_active is not None:
        conn.is_active = body.is_active
    conn.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(conn)
    return _to_out(conn)


@router.delete("/connections/{conn_id}", status_code=204)
async def delete_connection(
    conn_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(McpConnection).where(McpConnection.id == uuid.UUID(conn_id)))
    conn = result.scalar_one_or_none()
    if not conn or str(conn.tenant_id) != user["tenant_id"]:
        raise HTTPException(404, "Not found")
    await db.delete(conn)
    await db.commit()


@router.post("/connections/{conn_id}/test")
async def test_connection(
    conn_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Ping the MCP endpoint to verify connectivity."""
    result = await db.execute(select(McpConnection).where(McpConnection.id == uuid.UUID(conn_id)))
    conn = result.scalar_one_or_none()
    if not conn or str(conn.tenant_id) != user["tenant_id"]:
        raise HTTPException(404, "Not found")

    ok = False
    msg = ""
    plain_key = decrypt_secret(conn.api_key) if conn.api_key else ""
    try:
        headers = {}
        if plain_key:
            headers["Authorization"] = f"Bearer {plain_key}"

        if conn.conn_type == "loki":
            test_url = (conn.url.rstrip("/")) + "/ready"
        elif conn.conn_type == "datadog":
            test_url = "https://api.datadoghq.com/api/v1/validate"
            if plain_key:
                headers["DD-API-KEY"] = plain_key
                headers.pop("Authorization", None)
        else:
            test_url = conn.url

        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.get(test_url, headers=headers)
            if resp.status_code < 400:
                ok = True
                msg = f"Connected — HTTP {resp.status_code}"
            else:
                msg = f"HTTP {resp.status_code}: {resp.text[:200]}"
    except Exception as e:
        msg = str(e)[:300]

    conn.last_tested_at = datetime.now(timezone.utc)
    conn.last_test_ok = ok
    conn.last_test_msg = msg
    await db.commit()

    logger.info("mcp_connection_tested", id=conn_id, ok=ok, msg=msg)
    return {"ok": ok, "message": msg}


@router.get("/connections/{conn_id}/query")
async def query_mcp(
    conn_id: str,
    q: str = "",
    last_minutes: int = 60,
    limit: int = 50,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Query an MCP log source. The agent also calls this internally.
    Returns lines as plain text for LLM consumption.
    """
    result = await db.execute(select(McpConnection).where(McpConnection.id == uuid.UUID(conn_id)))
    conn = result.scalar_one_or_none()
    if not conn or str(conn.tenant_id) != user["tenant_id"]:
        raise HTTPException(404, "Not found")
    if not conn.is_active:
        raise HTTPException(400, "Connection is disabled")

    try:
        lines = await _query_source(conn, q, last_minutes, limit)
        return {"lines": lines, "count": len(lines)}
    except Exception as e:
        raise HTTPException(502, f"Query failed: {e}")


async def _query_source(conn: McpConnection, q: str, last_minutes: int, limit: int) -> list[str]:
    """Internal helper — used by the agent executor to pull log context."""
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    start = now - timedelta(minutes=last_minutes)

    headers: dict = {}
    plain_key = decrypt_secret(conn.api_key) if conn.api_key else ""
    if plain_key:
        headers["Authorization"] = f"Bearer {plain_key}"

    if conn.conn_type == "loki":
        logql = q or conn.config.get("default_query", '{service=~".+"}')
        if conn.config.get("filter") and not q:
            logql += f' |= "{conn.config["filter"]}"'
        params = {
            "query": logql,
            "start": str(int(start.timestamp() * 1e9)),
            "end": str(int(now.timestamp() * 1e9)),
            "limit": str(limit),
            "direction": "backward",
        }
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{conn.url.rstrip('/')}/loki/api/v1/query_range", params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        lines = []
        for stream in data.get("data", {}).get("result", []):
            for ts, line in stream.get("values", []):
                dt = datetime.fromtimestamp(int(ts) / 1e9, tz=timezone.utc).isoformat()
                lines.append(f"[{dt}] {line}")
        return lines[:limit]

    elif conn.conn_type == "custom_http":
        # Generic HTTP endpoint — expects {"logs": [...]} or plain text
        params: dict = {}
        if q:
            params["q"] = q
        params["limit"] = limit
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(conn.url, params=params, headers=headers)
            resp.raise_for_status()
        try:
            data = resp.json()
            if isinstance(data, list):
                return [str(item) for item in data[:limit]]
            if "logs" in data:
                return [str(l) for l in data["logs"][:limit]]
            return [resp.text[:2000]]
        except Exception:
            return [resp.text[:2000]]

    else:
        return [f"[{conn.conn_type}] Direct query not yet implemented for this type"]


# Expose for use by agent executor
async def get_active_mcp_context(tenant_id: str, db: AsyncSession, task_context: str = "") -> str:
    """
    Called by the agent executor — fetches recent logs from all active MCP
    connections and returns them as a compact context string for the LLM.
    """
    result = await db.execute(
        select(McpConnection).where(
            McpConnection.tenant_id == uuid.UUID(tenant_id),
            McpConnection.is_active == True,
        )
    )
    conns = result.scalars().all()
    if not conns:
        return ""

    parts: list[str] = ["=== External MCP Context ==="]
    for conn in conns:
        try:
            lines = await _query_source(conn, "", 30, 20)
            if lines:
                parts.append(f"\n--- {conn.name} ({conn.conn_type}) ---")
                parts.extend(lines[:10])
        except Exception:
            pass  # Don't fail the agent run if MCP is unreachable

    return "\n".join(parts) if len(parts) > 1 else ""
