"""Agent session API — Devin-style session CRUD + live event stream."""

from __future__ import annotations

import asyncio
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.agent.session_hub import session_event_hub
from app.agent.session_runner import start_session_task
from app.core.config import settings
from app.core.security import get_current_user, decode_token
from app.db.session import async_session_factory
from app.models.agent_session import AgentSession, SessionEventRecord
from app.models.user import User
from app.schemas.agent_session import (
    SessionCreate,
    SessionEventRecordResponse,
    SessionListItem,
    SessionMessageCreate,
    SessionResponse,
)

router = APIRouter(prefix="/sessions", tags=["sessions"])


def _session_response(session: AgentSession) -> SessionResponse:
    return SessionResponse(
        id=session.id,
        user_id=session.user_id,
        conversation_id=session.conversation_id,
        title=session.title,
        prompt=session.prompt,
        mode=session.mode,
        status=session.status,
        repository_url=session.repository_url,
        repository_owner=session.repository_owner,
        repository_name=session.repository_name,
        branch=session.branch,
        plan=session.plan or {},
        current_step_index=session.current_step_index,
        step_summaries=session.step_summaries or [],
        devbox_type=session.devbox_type,
        devbox_ref=session.devbox_ref,
        github_run_id=session.github_run_id,
        github_run_url=session.github_run_url,
        pr_url=session.pr_url,
        pr_number=session.pr_number,
        result=session.result or {},
        created_at=session.created_at,
        updated_at=session.updated_at,
        completed_at=session.completed_at,
    )


async def _get_user_github_token(user: User, token: str | None) -> str | None:
    if token:
        payload = decode_token(token)
        if payload:
            return payload.get("github_token")
    return None


async def _get_ollama_creds(user_id: uuid.UUID) -> tuple[str, str, str]:
    ollama_key = settings.OLLAMA_API_KEY or ""
    ollama_base = settings.OLLAMA_API_BASE or "https://ollama.com"
    ollama_model = settings.OLLAMA_MODEL or "qwen3-coder:480b"
    try:
        from app.models.user_settings import UserSettings
        from app.core.crypto import decrypt_value
        async with async_session_factory() as db:
            row = await db.scalar(
                select(UserSettings).where(UserSettings.user_id == user_id)
            )
            if row and row.api_keys:
                cfg = row.api_keys.get("ollama") or {}
                if cfg.get("key"):
                    ollama_key = decrypt_value(cfg["key"])
                if cfg.get("base_url"):
                    ollama_base = cfg["base_url"]
    except Exception:
        pass
    return ollama_key, ollama_base, ollama_model


@router.post("", response_model=SessionResponse)
async def create_session(
    body: SessionCreate,
    request: Request,
    user: User = Depends(get_current_user),
    token: Optional[str] = Query(None),
) -> SessionResponse:
    """Create a new agent session and start execution in the background."""
    title = body.title or body.prompt.strip()[:60]
    if len(body.prompt) > 60 and not body.title:
        title += "…"

    async with async_session_factory() as db:
        session = AgentSession(
            user_id=user.id,
            conversation_id=body.conversation_id,
            title=title,
            prompt=body.prompt.strip(),
            mode=body.mode,
            status="queued",
            repository_url=body.repository_url,
            repository_owner=body.repository_owner,
            repository_name=body.repository_name,
            branch=body.branch,
            devbox_type="github_actions" if body.repository_owner else "local",
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)
        session_id = session.id

    jwt_token = token or ""
    github_token = await _get_user_github_token(user, jwt_token)
    ollama_key, ollama_base, ollama_model = await _get_ollama_creds(user.id)
    base_url = str(request.base_url).rstrip("/")

    start_session_task(
        session_id,
        github_token=github_token,
        devbuddy_url=f"{base_url}/api/v1",
        devbuddy_token=jwt_token,
        ollama_key=ollama_key,
        ollama_base=ollama_base,
        ollama_model=ollama_model,
    )

    async with async_session_factory() as db:
        result = await db.execute(select(AgentSession).where(AgentSession.id == session_id))
        session = result.scalar_one()
        return _session_response(session)


@router.get("", response_model=List[SessionListItem])
async def list_sessions(
    user: User = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=100),
) -> List[SessionListItem]:
    async with async_session_factory() as db:
        result = await db.execute(
            select(AgentSession)
            .where(AgentSession.user_id == user.id)
            .order_by(AgentSession.updated_at.desc())
            .limit(limit)
        )
        sessions = result.scalars().all()
        return [SessionListItem.model_validate(s) for s in sessions]


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
) -> SessionResponse:
    async with async_session_factory() as db:
        result = await db.execute(
            select(AgentSession).where(
                AgentSession.id == session_id,
                AgentSession.user_id == user.id,
            )
        )
        session = result.scalar_one_or_none()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        return _session_response(session)


@router.get("/{session_id}/events", response_model=List[SessionEventRecordResponse])
async def list_session_events(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    after_seq: int = Query(0, ge=0),
) -> List[SessionEventRecordResponse]:
    async with async_session_factory() as db:
        session = await db.scalar(
            select(AgentSession).where(
                AgentSession.id == session_id,
                AgentSession.user_id == user.id,
            )
        )
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        result = await db.execute(
            select(SessionEventRecord)
            .where(
                SessionEventRecord.session_id == session_id,
                SessionEventRecord.seq > after_seq,
            )
            .order_by(SessionEventRecord.seq)
        )
        events = result.scalars().all()
        return [SessionEventRecordResponse.model_validate(e) for e in events]


@router.get("/{session_id}/stream")
async def stream_session_events(
    session_id: uuid.UUID,
    token: Optional[str] = Query(None),
    after_seq: int = Query(0, ge=0),
):
    """SSE stream of session events (live + catch-up)."""
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")

    email = payload.get("email") or payload.get("sub")
    async with async_session_factory() as db:
        from app.models.user import User as UserModel
        user = await db.scalar(select(UserModel).where(UserModel.email == email.lower()))
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        session = await db.scalar(
            select(AgentSession).where(
                AgentSession.id == session_id,
                AgentSession.user_id == user.id,
            )
        )
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Replay persisted events
        result = await db.execute(
            select(SessionEventRecord)
            .where(
                SessionEventRecord.session_id == session_id,
                SessionEventRecord.seq > after_seq,
            )
            .order_by(SessionEventRecord.seq)
        )
        backlog = result.scalars().all()
        session_status = session.status

    async def event_generator():
        for record in backlog:
            event = session_event_hub.format_event(
                session_id, record.seq, record.event_type, record.payload
            )
            yield session_event_hub.sse_line(event)

        if session_status in ("completed", "failed", "terminated"):
            return

        queue = await session_event_hub.subscribe(session_id)
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield session_event_hub.sse_line(event)
                    if event.get("type") == "session_status" and event.get("payload", {}).get("status") in (
                        "completed", "failed", "terminated"
                    ):
                        break
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            await session_event_hub.unsubscribe(session_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{session_id}/messages")
async def send_session_message(
    session_id: uuid.UUID,
    body: SessionMessageCreate,
    user: User = Depends(get_current_user),
) -> dict:
    """Send follow-up instruction to a running or paused session."""
    async with async_session_factory() as db:
        session = await db.scalar(
            select(AgentSession).where(
                AgentSession.id == session_id,
                AgentSession.user_id == user.id,
            )
        )
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        session.prompt = f"{session.prompt}\n\nFollow-up: {body.content}"
        await db.commit()

    return {"accepted": True, "session_id": str(session_id)}


@router.post("/{session_id}/terminate")
async def terminate_session(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
) -> dict:
    async with async_session_factory() as db:
        session = await db.scalar(
            select(AgentSession).where(
                AgentSession.id == session_id,
                AgentSession.user_id == user.id,
            )
        )
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        session.status = "terminated"
        await db.commit()

    from app.agent.session_runner import _running
    task = _running.get(session_id)
    if task and not task.done():
        task.cancel()

    return {"terminated": True, "session_id": str(session_id)}
