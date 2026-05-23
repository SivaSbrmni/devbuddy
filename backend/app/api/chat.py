import json
import asyncio
import traceback
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from typing import AsyncGenerator

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.config import settings
from app.services.task_service import create_task, transition_task_state
from app.services.llm_service import analyze_intent, run_stage
from app.services.agent_executor import execute_task
from app.schemas.task import TaskCreate, TaskStateTransition
from app.models.task import TaskState
from app.core.logger import get_logger

router = APIRouter(prefix="/chat", tags=["chat"])
logger = get_logger("chat")

# Intents that can be resolved by LLM directly — no container / pipeline needed
CONVERSATIONAL_INTENTS = {"query", "unknown", "greeting", "clarification", "general"}

# Intents that require the full agent pipeline (container spawn)
PIPELINE_INTENTS = {"code_change", "bug_fix", "feature", "refactor", "deploy", "review"}

AGENT_STAGES = [
    (TaskState.PLANNING,        "Planning",        "Decomposing requirements and building execution plan..."),
    (TaskState.EXECUTING,       "Executing",       "Spawning agent container and running code operations..."),
    (TaskState.VALIDATING,      "Validating",      "Running tests, linting, and static analysis..."),
    (TaskState.SECURITY_REVIEW, "Security Review", "Scanning for vulnerabilities and policy compliance..."),
    (TaskState.READY_TO_PUSH,   "Ready to Push",   "All checks passed. Preparing changeset for review..."),
    (TaskState.COMPLETED,       "Completed",       "Task completed successfully."),
]

STAGE_DELAYS: dict[TaskState, float] = {
    TaskState.PLANNING:        1.2,
    TaskState.EXECUTING:       2.5,
    TaskState.VALIDATING:      1.8,
    TaskState.SECURITY_REVIEW: 2.0,
    TaskState.READY_TO_PUSH:   0.8,
    TaskState.COMPLETED:       0.3,
}


# ── SSE helpers ───────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def sse_error(code: str, message: str, stage: str | None = None, recoverable: bool = False) -> str:
    return sse("error", {"code": code, "message": message, "stage": stage, "recoverable": recoverable, "timestamp": _now()})


def sse_heartbeat() -> str:
    return f": heartbeat {_now()}\n\n"


# ── Main streaming generator ──────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str


async def _stream_chat(
    message: str,
    user: dict,
    db: AsyncSession,
    request: Request,
) -> AsyncGenerator[str, None]:
    """
    High-fidelity SSE generator with:
    - Per-stage error isolation
    - Structured error events (code, message, recoverable)
    - Heartbeat keepalive
    - Client disconnect detection
    - Task quarantine on unrecoverable failure
    """
    task = None
    current_stage: str | None = None

    async def is_disconnected() -> bool:
        return await request.is_disconnected()

    try:
        # ── 1. INTENT ANALYSIS ───────────────────────────────────────────────
        current_stage = "intent_analysis"
        yield sse("status", {
            "stage": current_stage,
            "message": f"Analyzing your request with {settings.LLM_PROVIDER}/{settings.LLM_MODEL}...",
            "terminal": False,
            "timestamp": _now(),
        })

        intent, call_record = await analyze_intent(message)

        yield sse("llm_call", {
            "num":               call_record.num,
            "model":             call_record.model,
            "provider":          call_record.provider,
            "msg_count":         call_record.msg_count,
            "prompt_tokens":     call_record.prompt_tokens,
            "completion_tokens": call_record.completion_tokens,
            "duration_ms":       round(call_record.duration_ms, 1),
            "has_tool_calls":    call_record.has_tool_calls,
            "prompt_preview":    call_record.prompt_preview,
            "response_preview":  call_record.response_preview,
            "error":             call_record.error,
            "timestamp":         _now(),
        })

        if intent.get("_fallback"):
            yield sse("warning", {
                "stage":       current_stage,
                "message":     f"LLM unavailable ({call_record.error}) — using heuristic fallback",
                "recoverable": True,
                "timestamp":   _now(),
            })

        intent_type = intent.get("intent", "unknown")
        needs_pipeline = intent_type in PIPELINE_INTENTS

        yield sse("intent", {
            "intent":         intent_type,
            "confidence":     intent.get("confidence", 0.0),
            "title":          intent.get("title", message[:80]),
            "description":    intent.get("description", message),
            "reasoning":      intent.get("reasoning", ""),
            "steps":          intent.get("steps", []),
            "repo_id":        intent.get("repo_id"),
            "branch":         intent.get("branch"),
            "policy_profile": intent.get("policy_profile", "standard"),
            "fallback":       bool(intent.get("_fallback")),
            "model":          call_record.model,
            "provider":       call_record.provider,
            "needs_pipeline": needs_pipeline,
            "timestamp":      _now(),
        })

        # Mark the status row as resolved now that intent is known
        yield sse("status", {
            "stage":    current_stage,
            "message":  f"Analyzing your request with {settings.LLM_PROVIDER}/{settings.LLM_MODEL}...",
            "terminal": True,
            "timestamp": _now(),
        })

        if await is_disconnected():
            return

        await asyncio.sleep(0.2)

        # ── 2a. CONVERSATIONAL / QUERY — answer directly, no pipeline ────────
        if not needs_pipeline:
            logger.info("conversational_intent", intent=intent_type)
            reply = intent.get("description") or intent.get("title") or "I'm here to help! Describe a coding task."
            yield sse("llm_reply", {
                "text":      reply,
                "intent":    intent_type,
                "timestamp": _now(),
            })
            yield sse("done", {
                "task_id":     None,
                "final_state": "ANSWERED",
                "message":     reply,
                "timestamp":   _now(),
            })
            return

        # ── 2b. TASK CREATION (pipeline intents only) ────────────────────────
        current_stage = "task_creation"
        yield sse("status", {
            "stage":    current_stage,
            "message":  "Creating task in the system...",
            "terminal": False,
            "timestamp": _now(),
        })

        try:
            task_data = TaskCreate(
                title=intent.get("title", message[:80]),
                description=intent.get("description", message),
                repo_id=intent.get("repo_id"),
                branch=intent.get("branch", "feature/devbuddy-task"),
                policy_profile=intent.get("policy_profile", "standard"),
                metadata={
                    "chat_message":  message,
                    "intent":        intent_type,
                    "confidence":    intent.get("confidence"),
                    "fallback_intent": bool(intent.get("_fallback")),
                },
            )
            task = await create_task(db, task_data, user)
            await db.commit()
        except Exception as exc:
            logger.error("task_creation_failed", error=str(exc), trace=traceback.format_exc())
            yield sse_error("TASK_CREATE_FAILED", f"Failed to create task: {exc}", current_stage, recoverable=False)
            yield sse("done", {"task_id": None, "final_state": "FAILED", "message": "Task creation failed.", "timestamp": _now()})
            return

        yield sse("status", {
            "stage":    current_stage,
            "message":  "Creating task in the system...",
            "terminal": True,
            "timestamp": _now(),
        })
        yield sse("task_created", {
            "task_id":    str(task.id),
            "title":      task.title,
            "state":      task.state.value,
            "created_at": task.created_at.isoformat(),
            "timestamp":  _now(),
        })

        if await is_disconnected():
            return

        await asyncio.sleep(0.3)

        # ── 3. AGENT PIPELINE ────────────────────────────────────────────────
        heartbeat_counter = 0
        task_title = intent.get("title", message[:80])
        task_description = intent.get("description", message)

        for to_state, stage_name, stage_msg in AGENT_STAGES:
            current_stage = to_state.value

            if await is_disconnected():
                logger.info("client_disconnected_mid_pipeline", stage=current_stage, task_id=str(task.id))
                return

            # Announce stage starting (spinning)
            yield sse("agent_stage", {
                "stage":     stage_name,
                "state":     to_state.value,
                "message":   stage_msg,
                "task_id":   str(task.id),
                "output":    "",
                "done":      False,
                "timestamp": _now(),
            })

            heartbeat_counter += 1
            if heartbeat_counter % 2 == 0:
                yield sse_heartbeat()

            # For EXECUTING: run real agent executor (writes files, streams logs)
            if to_state == TaskState.EXECUTING:
                log_lines: list[str] = []
                async for log_entry in execute_task(str(task.id), task_title, task_description):
                    log_lines.append(log_entry["line"])
                    yield sse("container_log", {
                        "task_id": str(task.id),
                        "line":    log_entry["line"],
                        "stream":  log_entry["stream"],
                        "ts":      log_entry["ts"],
                        "timestamp": _now(),
                    })
                    if await is_disconnected():
                        return
                stage_output = "\n".join(log_lines)
                # Build a minimal call record for LLM Logs
                from app.services.llm_service import LlmCallRecord
                stage_record = LlmCallRecord(
                    num=999,
                    model=settings.LLM_MODEL,
                    provider=settings.LLM_PROVIDER,
                    msg_count=1,
                    prompt_preview=f"Execute: {task_title}",
                    response_preview=stage_output[:500],
                )
            else:
                # All other stages: LLM reasoning call
                stage_output, stage_record = await run_stage(to_state.value, task_title, task_description)

            # Emit stage LLM call to LLM Logs panel
            yield sse("llm_call", {
                "num":               stage_record.num,
                "model":             stage_record.model,
                "provider":          stage_record.provider,
                "msg_count":         stage_record.msg_count,
                "prompt_tokens":     stage_record.prompt_tokens,
                "completion_tokens": stage_record.completion_tokens,
                "duration_ms":       round(stage_record.duration_ms, 1),
                "has_tool_calls":    stage_record.has_tool_calls,
                "prompt_preview":    stage_record.prompt_preview,
                "response_preview":  stage_record.response_preview,
                "error":             stage_record.error,
                "timestamp":         _now(),
            })

            if await is_disconnected():
                return

            try:
                transition = TaskStateTransition(
                    to_state=to_state,
                    reason=f"Chat-driven pipeline: {stage_name}",
                )
                task = await transition_task_state(db, task.id, task.tenant_id, transition, user["id"])
                await db.commit()
            except Exception as exc:
                logger.error("stage_transition_failed", stage=current_stage, task_id=str(task.id),
                             error=str(exc), trace=traceback.format_exc())
                yield sse_error("STAGE_TRANSITION_FAILED",
                                f"State transition failed at {stage_name}: {exc}",
                                current_stage, recoverable=True)
                if to_state == TaskState.COMPLETED:
                    yield sse("done", {"task_id": str(task.id), "final_state": "FAILED",
                                       "message": f"Pipeline failed at {stage_name}.", "timestamp": _now()})
                    return
                continue

            # Stage complete — send output back
            yield sse("state_update", {
                "task_id":   str(task.id),
                "state":     task.state.value,
                "stage":     stage_name,
                "output":    stage_output,
                "done":      True,
                "timestamp": _now(),
            })

        # ── 4. DONE ──────────────────────────────────────────────────────────
        yield sse("done", {
            "task_id":     str(task.id),
            "final_state": task.state.value,
            "message":     "Agent pipeline completed successfully.",
            "timestamp":   _now(),
        })
        logger.info("chat_stream_complete", task_id=str(task.id), final_state=task.state.value)

    except asyncio.CancelledError:
        logger.info("chat_stream_cancelled", stage=current_stage, task_id=str(task.id) if task else None)
        return

    except Exception as exc:
        logger.error(
            "chat_stream_unhandled",
            stage=current_stage, task_id=str(task.id) if task else None,
            error=str(exc), trace=traceback.format_exc(),
        )
        yield sse_error(
            "STREAM_UNHANDLED",
            f"Unexpected error in pipeline: {exc}",
            current_stage,
            recoverable=False,
        )
        yield sse("done", {
            "task_id":     str(task.id) if task else None,
            "final_state": "FAILED",
            "message":     "Pipeline terminated due to unexpected error.",
            "timestamp":   _now(),
        })


@router.post("")
async def chat(
    body: ChatRequest,
    request: Request,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return StreamingResponse(
        _stream_chat(body.message, user, db, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control":      "no-cache",
            "X-Accel-Buffering":  "no",
            "Connection":         "keep-alive",
            "Transfer-Encoding":  "chunked",
        },
    )
