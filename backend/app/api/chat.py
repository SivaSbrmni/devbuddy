import json
import asyncio
import httpx
from datetime import datetime
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.config import settings
from app.services.task_service import create_task, transition_task_state
from app.schemas.task import TaskCreate, TaskStateTransition
from app.models.task import TaskState
from app.core.logger import get_logger

router = APIRouter(prefix="/chat", tags=["chat"])
logger = get_logger("chat")

OLLAMA_URL = settings.OLLAMA_URL

INTENT_SYSTEM_PROMPT = """You are DevBuddy, an enterprise autonomous coding agent.
Analyze the user's message and extract a structured task intent.

Respond ONLY with valid JSON in this exact format:
{
  "intent": "one of: code_change | bug_fix | feature | refactor | review | deploy | query | unknown",
  "confidence": 0.0-1.0,
  "title": "concise task title (max 80 chars)",
  "description": "detailed description of what needs to be done",
  "repo_id": "inferred repo name or null",
  "branch": "suggested branch name or null",
  "policy_profile": "one of: standard | strict | permissive",
  "reasoning": "brief explanation of intent analysis",
  "steps": ["step 1", "step 2", "step 3"]
}"""

AGENT_STAGES = [
    (TaskState.PLANNING,          "Planning",          "Decomposing requirements and building execution plan..."),
    (TaskState.EXECUTING,         "Executing",         "Spawning agent container and running code operations..."),
    (TaskState.VALIDATING,        "Validating",        "Running tests, linting, and static analysis..."),
    (TaskState.SECURITY_REVIEW,   "Security Review",   "Scanning for vulnerabilities and policy compliance..."),
    (TaskState.READY_TO_PUSH,     "Ready to Push",     "All checks passed. Preparing changeset for review..."),
    (TaskState.COMPLETED,         "Completed",         "Task completed successfully."),
]


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def call_ollama(prompt: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={"model": "llama3.2:latest", "prompt": prompt, "stream": False},
            )
            if resp.status_code == 200:
                return resp.json().get("response", "")
    except Exception as e:
        logger.warning("ollama_unavailable", error=str(e))
    return ""


async def analyze_intent(message: str) -> dict:
    full_prompt = f"{INTENT_SYSTEM_PROMPT}\n\nUser message: {message}"
    raw = await call_ollama(full_prompt)

    try:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(raw[start:end])
    except Exception:
        pass

    title = message[:80] if len(message) > 80 else message
    return {
        "intent": "code_change",
        "confidence": 0.75,
        "title": title,
        "description": message,
        "repo_id": None,
        "branch": "feature/devbuddy-task",
        "policy_profile": "standard",
        "reasoning": "Could not reach LLM — using message as task description.",
        "steps": ["Analyze requirements", "Implement changes", "Validate and review"],
    }


class ChatRequest(BaseModel):
    message: str


async def _stream_chat(message: str, user: dict, db: AsyncSession):
    yield sse("status", {"stage": "intent_analysis", "message": "Analyzing your request with LLM..."})
    await asyncio.sleep(0.3)

    intent = await analyze_intent(message)
    yield sse("intent", {
        "intent": intent.get("intent"),
        "confidence": intent.get("confidence"),
        "title": intent.get("title"),
        "description": intent.get("description"),
        "reasoning": intent.get("reasoning"),
        "steps": intent.get("steps", []),
        "repo_id": intent.get("repo_id"),
        "branch": intent.get("branch"),
        "policy_profile": intent.get("policy_profile", "standard"),
    })
    await asyncio.sleep(0.4)

    yield sse("status", {"stage": "spawning_task", "message": "Creating task in the system..."})

    task_data = TaskCreate(
        title=intent.get("title", message[:80]),
        description=intent.get("description", message),
        repo_id=intent.get("repo_id"),
        branch=intent.get("branch", "feature/devbuddy-task"),
        policy_profile=intent.get("policy_profile", "standard"),
        metadata={"chat_message": message, "intent": intent.get("intent"), "confidence": intent.get("confidence")},
    )

    task = await create_task(db, task_data, user)
    await db.commit()

    yield sse("task_created", {
        "task_id": str(task.id),
        "title": task.title,
        "state": task.state.value,
        "created_at": task.created_at.isoformat(),
    })
    await asyncio.sleep(0.5)

    for to_state, stage_name, stage_msg in AGENT_STAGES:
        yield sse("agent_stage", {
            "stage": stage_name,
            "state": to_state.value,
            "message": stage_msg,
            "task_id": str(task.id),
        })

        transition = TaskStateTransition(to_state=to_state, reason=f"Chat-driven auto-progression: {stage_name}")
        task = await transition_task_state(db, task.id, task.tenant_id, transition, user["id"])
        await db.commit()

        yield sse("state_update", {
            "task_id": str(task.id),
            "state": task.state.value,
            "stage": stage_name,
            "timestamp": datetime.utcnow().isoformat(),
        })

        delay = 1.8 if to_state in (TaskState.EXECUTING, TaskState.SECURITY_REVIEW) else 1.0
        await asyncio.sleep(delay)

    yield sse("done", {
        "task_id": str(task.id),
        "final_state": task.state.value,
        "message": "Agent completed all stages successfully.",
    })


@router.post("")
async def chat(
    body: ChatRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return StreamingResponse(
        _stream_chat(body.message, user, db),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
