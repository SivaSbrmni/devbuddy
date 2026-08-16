"""Agent session API — Devin-style session CRUD + live event stream."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select

from app.agent.session_hub import session_event_hub
from app.agent.session_runner import (
    persist_session_event,
    start_session_task,
)
from app.core.config import settings
from app.core.security import (
    create_session_scoped_token,
    decode_token,
    extract_github_token,
    get_current_user,
    security_scheme,
)
from app.db.session import async_session_factory
from app.models.agent_session import AgentSession, SessionEventRecord
from app.models.conversation import Conversation
from app.models.user import User
from app.schemas.agent_session import (
    SessionCreate,
    SessionEventRecordResponse,
    SessionListItem,
    SessionMessageCreate,
    SessionResponse,
)

router = APIRouter(prefix="/sessions", tags=["sessions"])

_TERMINAL_STATUSES = frozenset({"completed", "failed", "terminated"})


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


def _resolve_jwt_token(
    token: Optional[str],
    credentials: Optional[HTTPAuthorizationCredentials],
) -> str:
    return token or (credentials.credentials if credentials else "")


async def _get_user_github_token(
    token: Optional[str],
    credentials: Optional[HTTPAuthorizationCredentials],
) -> str | None:
    jwt_token = _resolve_jwt_token(token, credentials)
    if not jwt_token:
        return None
    payload = decode_token(jwt_token)
    return extract_github_token(payload)


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


async def _validate_conversation_owner(
    db,
    conversation_id: uuid.UUID | None,
    user_id: uuid.UUID,
) -> None:
    if not conversation_id:
        return
    conv = await db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
        )
    )
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")


@router.post("", response_model=SessionResponse)
async def create_session(
    body: SessionCreate,
    request: Request,
    user: User = Depends(get_current_user),
    token: Optional[str] = Query(None),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
) -> SessionResponse:
    """Create a new agent session and start execution in the background."""
    has_repo = bool(body.repository_owner and body.repository_name)
    github_token = await _get_user_github_token(token, credentials)

    if has_repo and not github_token:
        raise HTTPException(
            status_code=400,
            detail="GitHub is not connected. Connect GitHub before starting a repository session.",
        )

    title = body.title or body.prompt.strip()[:60]
    if len(body.prompt) > 60 and not body.title:
        title += "…"

    async with async_session_factory() as db:
        await _validate_conversation_owner(db, body.conversation_id, user.id)
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
            devbox_type="github_actions" if has_repo else "local",
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)
        session_id = session.id

    ollama_key, ollama_base, ollama_model = await _get_ollama_creds(user.id)
    base_url = str(request.base_url).rstrip("/")
    session_token = create_session_scoped_token(user.email, str(session_id))

    try:
        start_session_task(
            session_id,
            github_token=github_token,
            devbuddy_url=f"{base_url}/api/v1",
            devbuddy_token=session_token,
            ollama_key=ollama_key,
            ollama_base=ollama_base,
            ollama_model=ollama_model,
        )
    except Exception as exc:
        async with async_session_factory() as db:
            result = await db.execute(select(AgentSession).where(AgentSession.id == session_id))
            session = result.scalar_one_or_none()
            if session:
                session.status = "failed"
                session.result = {"error": f"Failed to start session: {exc}"}
                session.completed_at = datetime.now(timezone.utc)
                await db.commit()
        raise HTTPException(status_code=500, detail="Failed to start session") from exc

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
    """SSE stream of session events (DB-backed catch-up + live poll)."""
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")

    email = payload.get("email") or payload.get("sub")
    async with async_session_factory() as db:
        user = await db.scalar(select(User).where(User.email == email.lower()))
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

    async def event_generator():
        last_seq = after_seq
        while True:
            async with async_session_factory() as db:
                session_row = await db.scalar(
                    select(AgentSession).where(AgentSession.id == session_id)
                )
                if not session_row:
                    return

                result = await db.execute(
                    select(SessionEventRecord)
                    .where(
                        SessionEventRecord.session_id == session_id,
                        SessionEventRecord.seq > last_seq,
                    )
                    .order_by(SessionEventRecord.seq)
                )
                records = result.scalars().all()

            for record in records:
                event = session_event_hub.format_event(
                    session_id, record.seq, record.event_type, record.payload
                )
                yield session_event_hub.sse_line(event)
                last_seq = record.seq
                if (
                    event.get("type") == "session_status"
                    and event.get("payload", {}).get("status") in _TERMINAL_STATUSES
                ):
                    return

            if session_row.status in _TERMINAL_STATUSES and not records:
                return

            yield ": keepalive\n\n"
            await asyncio.sleep(1.5)

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
    request: Request,
    user: User = Depends(get_current_user),
    token: Optional[str] = Query(None),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
) -> dict:
    """Send follow-up instruction and restart a completed/failed session."""
    async with async_session_factory() as db:
        session = await db.scalar(
            select(AgentSession).where(
                AgentSession.id == session_id,
                AgentSession.user_id == user.id,
            )
        )
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        if session.status in ("queued", "planning", "running"):
            raise HTTPException(
                status_code=409,
                detail="Session is still running. Wait for it to finish before sending a follow-up.",
            )
        if session.status == "terminated":
            raise HTTPException(status_code=400, detail="Cannot send follow-up to a terminated session")

        has_repo = bool(session.repository_owner and session.repository_name)
        github_token = await _get_user_github_token(token, credentials)
        if has_repo and not github_token:
            raise HTTPException(
                status_code=400,
                detail="GitHub is not connected. Connect GitHub to continue this repository session.",
            )

        session.prompt = f"{session.prompt}\n\nFollow-up: {body.content.strip()}"
        session.status = "queued"
        session.completed_at = None
        session.result = {}
        await db.commit()

    await persist_session_event(
        session_id,
        "thinking",
        {"content": f"Follow-up: {body.content.strip()}", "phase": "follow-up"},
    )
    await persist_session_event(session_id, "session_status", {"status": "queued"})

    ollama_key, ollama_base, ollama_model = await _get_ollama_creds(user.id)
    base_url = str(request.base_url).rstrip("/")
    session_token = create_session_scoped_token(user.email, str(session_id))

    start_session_task(
        session_id,
        github_token=github_token,
        devbuddy_url=f"{base_url}/api/v1",
        devbuddy_token=session_token,
        ollama_key=ollama_key,
        ollama_base=ollama_base,
        ollama_model=ollama_model,
    )

    return {"accepted": True, "session_id": str(session_id), "restarted": True}


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
        if session.status in _TERMINAL_STATUSES:
            return {"terminated": True, "session_id": str(session_id), "already_terminal": True}

        session.status = "terminated"
        session.completed_at = datetime.now(timezone.utc)
        await db.commit()

    from app.agent.session_runner import _running

    task = _running.get(session_id)
    if task and not task.done():
        task.cancel()

    await persist_session_event(session_id, "session_status", {"status": "terminated"})

    return {"terminated": True, "session_id": str(session_id)}
