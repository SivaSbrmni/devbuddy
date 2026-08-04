"""Session runner — orchestrates brain + devbox execution with persisted events."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy import select, func

from app.agent.brain import DevBuddyBrain
from app.agent.session_hub import session_event_hub
from app.db.session import async_session_factory
from app.llm.gateway import LLMGateway, initialize_gateway_for_user
from app.models.agent_session import AgentSession, SessionEventRecord

log = structlog.get_logger()

# Track running tasks so we don't double-start
_running: dict[uuid.UUID, asyncio.Task] = {}


async def _next_seq(db, session_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.coalesce(func.max(SessionEventRecord.seq), 0)).where(
            SessionEventRecord.session_id == session_id
        )
    )
    current = result.scalar() or 0
    return int(current) + 1


async def _persist_event(
    session_id: uuid.UUID,
    event_type: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    async with async_session_factory() as db:
        seq = await _next_seq(db, session_id)
        record = SessionEventRecord(
            session_id=session_id,
            seq=seq,
            event_type=event_type,
            payload=payload,
        )
        db.add(record)
        await db.commit()
        event = session_event_hub.format_event(session_id, seq, event_type, payload)
        await session_event_hub.publish(session_id, event)
        return event


async def _update_session(session_id: uuid.UUID, **fields: Any) -> None:
    async with async_session_factory() as db:
        result = await db.execute(
            select(AgentSession).where(AgentSession.id == session_id)
        )
        session = result.scalar_one_or_none()
        if not session:
            return
        for key, value in fields.items():
            setattr(session, key, value)
        await db.commit()


def _translate_cloud_event(cloud_type: str, payload: dict) -> tuple[str, dict] | None:
    """Map legacy cloud_runner SSE events to unified session events."""
    if cloud_type == "timeline":
        step = payload.get("step", "")
        status = payload.get("status", "")
        message = payload.get("message", "")
        if step in ("commit", "push"):
            return "shell", {"command": f"git {step}", "output": message, "exit_code": 0 if status == "done" else 1}
        return "thinking", {"content": message, "phase": step}
    if cloud_type == "think":
        return "thinking", {"content": payload.get("message", "")}
    if cloud_type == "tool_call":
        return "shell", {
            "command": f"{payload.get('tool', 'tool')} {json.dumps(payload.get('params', {}))[:120]}",
            "output": "",
            "exit_code": 0,
        }
    if cloud_type == "observe":
        return "thinking", {"content": payload.get("output", "")[:500]}
    if cloud_type == "file_change":
        return "file_change", {
            "path": payload.get("path", ""),
            "action": payload.get("action", "modified"),
            "diff": payload.get("diff", ""),
        }
    if cloud_type == "runner":
        return "devbox_status", {
            "state": payload.get("state", ""),
            "message": payload.get("message", ""),
            "run_url": payload.get("run_url", ""),
        }
    if cloud_type == "pr":
        return "pr_created", {
            "url": payload.get("url", ""),
            "number": payload.get("number", 0),
        }
    if cloud_type == "quality_gates":
        return "ci_status", {"gates": payload}
    if cloud_type == "error":
        return "error", {"message": payload.get("message", "Unknown error")}
    if cloud_type == "done":
        return "session_status", {"status": "completed", "summary": payload.get("summary", "")}
    if cloud_type == "log":
        return "shell", {"command": "log", "output": payload.get("message", ""), "exit_code": 0}
    return None


async def _run_github_devbox(
    session: AgentSession,
    emit,
    *,
    github_token: str,
    devbuddy_url: str,
    devbuddy_token: str,
    ollama_key: str = "",
    ollama_base: str = "",
    ollama_model: str = "",
) -> bool:
    from app.agents.cloud_runner import run_cloud_agent

    owner = session.repository_owner or ""
    repo = session.repository_name or ""
    pr_url = ""
    pr_number = 0
    run_url = ""
    success = False

    async for chunk in run_cloud_agent(
        task=session.prompt,
        owner=owner,
        repo=repo,
        github_token=github_token,
        devbuddy_url=devbuddy_url,
        devbuddy_token=devbuddy_token,
        conversation_id=str(session.conversation_id or ""),
        ollama_key=ollama_key,
        ollama_base=ollama_base,
        ollama_model=ollama_model,
    ):
        if not chunk.startswith("data: "):
            continue
        try:
            raw = json.loads(chunk[6:])
        except json.JSONDecodeError:
            continue

        cloud_type = raw.get("type", "")
        payload = raw.get("payload") or {}
        translated = _translate_cloud_event(cloud_type, payload)
        if translated:
            etype, epayload = translated
            await emit(etype, epayload)
            if etype == "pr_created":
                pr_url = epayload.get("url", "")
                pr_number = epayload.get("number", 0)
            if etype == "devbox_status" and epayload.get("run_url"):
                run_url = epayload["run_url"]
            if etype == "session_status" and epayload.get("status") == "completed":
                success = True
            if etype == "error":
                success = False

        if cloud_type == "runner" and payload.get("run_url"):
            run_url = payload.get("run_url", "")

    if pr_url:
        await _update_session(
            session.id,
            pr_url=pr_url,
            pr_number=pr_number or None,
            github_run_url=run_url or None,
        )
    return success


async def _run_chat_devbox(session: AgentSession, emit, user) -> bool:
    """No-repo path: stream LLM response as session output."""
    from app.llm.gateway import LLMGateway, initialize_gateway_for_user

    async with async_session_factory() as db:
        gateway = LLMGateway(user_id=user.id, db=db)
        await initialize_gateway_for_user(gateway, user)

        if not gateway.providers:
            await emit("error", {"message": "No LLM providers configured"})
            return False

        content = ""
        await emit("step_started", {"index": 0, "step": {"title": "Generating response"}})
        async for delta in gateway.stream(
            messages=[{"role": "user", "content": session.prompt}],
            task_type="coder",
        ):
            if delta:
                content += delta
                await emit("thinking", {"content": delta, "streaming": True})

        await emit("thinking", {"content": content, "streaming": False, "final": True})
        await _update_session(session.id, result={"content": content})
        return bool(content.strip())


async def execute_session(
    session_id: uuid.UUID,
    *,
    github_token: str | None = None,
    devbuddy_url: str = "",
    devbuddy_token: str = "",
    ollama_key: str = "",
    ollama_base: str = "",
    ollama_model: str = "",
) -> None:
    """Main session execution entrypoint (runs in background task)."""
    async with async_session_factory() as db:
        result = await db.execute(
            select(AgentSession).where(AgentSession.id == session_id)
        )
        session = result.scalar_one_or_none()
        if not session:
            return
        from app.models.user import User
        user_result = await db.execute(select(User).where(User.id == session.user_id))
        user = user_result.scalar_one()

    async def emit(event_type: str, payload: dict[str, Any]) -> None:
        await _persist_event(session_id, event_type, payload)

    try:
        await _update_session(session_id, status="planning")
        await emit("session_status", {"status": "planning"})

        brain = DevBuddyBrain()
        has_repo = bool(session.repository_owner and session.repository_name)

        gateway = None
        async with async_session_factory() as db:
            gateway = LLMGateway(user_id=user.id, db=db)
            await initialize_gateway_for_user(gateway, user)

        repo_context = ""
        if has_repo:
            repo_context = f"{session.repository_owner}/{session.repository_name}"

        plan = await brain.create_plan(
            session.prompt,
            has_repo=has_repo,
            repo_context=repo_context,
            gateway=gateway,
        )
        await _update_session(
            session_id,
            status="running",
            plan=plan.model_dump(),
        )
        await emit("plan_updated", {"plan": plan.model_dump()})
        await emit("session_status", {"status": "running"})

        if has_repo and github_token:
            # Advance through plan steps while cloud devbox runs
            step_index = 0

            async def on_cloud_event(etype: str, epayload: dict) -> None:
                nonlocal step_index
                await emit(etype, epayload)
                if etype == "thinking" and step_index < len(plan.steps) - 1:
                    phase = epayload.get("phase", "")
                    if phase in ("execution", "commit", "push", "pr"):
                        while step_index < len(plan.steps) - 1:
                            s = plan.steps[step_index]
                            s.status = "completed"
                            await emit("step_completed", {
                                "index": step_index,
                                "step": s.model_dump(),
                                "summary": s.title,
                                "success": True,
                            })
                            step_index += 1
                            if s.id in ("implement", "validate", "deliver"):
                                break

            success = await _run_github_devbox(
                session,
                on_cloud_event,
                github_token=github_token,
                devbuddy_url=devbuddy_url,
                devbuddy_token=devbuddy_token,
                ollama_key=ollama_key,
                ollama_base=ollama_base,
                ollama_model=ollama_model,
            )

            # Complete any remaining plan steps
            for i in range(step_index, len(plan.steps)):
                s = plan.steps[i]
                s.status = "completed" if success else "failed"
                await emit("step_completed", {
                    "index": i,
                    "step": s.model_dump(),
                    "summary": s.title,
                    "success": success,
                })

            if not success:
                await _update_session(session_id, status="failed", completed_at=datetime.now(timezone.utc))
                await emit("session_status", {"status": "failed"})
                return
        else:
            for i, step in enumerate(plan.steps):
                step.status = "active"
                await emit("step_started", {"index": i, "step": step.model_dump()})
                if i == len(plan.steps) - 1:
                    ok = await _run_chat_devbox(session, emit, user)
                    step.status = "completed" if ok else "failed"
                    await emit("step_completed", {
                        "index": i,
                        "step": step.model_dump(),
                        "summary": step.title,
                        "success": ok,
                    })
                    if not ok:
                        await _update_session(session_id, status="failed", completed_at=datetime.now(timezone.utc))
                        await emit("session_status", {"status": "failed"})
                        return
                else:
                    await emit("thinking", {"content": f"Analyzing: {step.title}"})
                    step.status = "completed"
                    await emit("step_completed", {
                        "index": i,
                        "step": step.model_dump(),
                        "summary": step.title,
                        "success": True,
                    })
                await asyncio.sleep(0.15)

        await _update_session(
            session_id,
            status="completed",
            completed_at=datetime.now(timezone.utc),
        )
        await emit("session_status", {"status": "completed"})

    except asyncio.CancelledError:
        await _update_session(session_id, status="terminated")
        await emit("session_status", {"status": "terminated"})
        raise
    except Exception as e:
        log.exception("session.run_failed", session_id=str(session_id), error=str(e))
        await _update_session(session_id, status="failed", result={"error": str(e)})
        await emit("error", {"message": str(e)})
        await emit("session_status", {"status": "failed"})
    finally:
        _running.pop(session_id, None)


def start_session_task(session_id: uuid.UUID, **kwargs: Any) -> asyncio.Task:
    if session_id in _running and not _running[session_id].done():
        return _running[session_id]
    task = asyncio.create_task(execute_session(session_id, **kwargs))
    _running[session_id] = task
    return task


def is_session_running(session_id: uuid.UUID) -> bool:
    task = _running.get(session_id)
    return task is not None and not task.done()
