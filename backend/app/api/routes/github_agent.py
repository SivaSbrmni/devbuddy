"""GitHub Agent API — SSE endpoint for the autonomous GitHub engineering agent."""

from __future__ import annotations

from typing import Optional, AsyncGenerator

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from jose import jwt
from pydantic import BaseModel

from app.core.config import settings
from app.core.model_router import model_router
from app.agents.github_agent import run_github_agent

router = APIRouter(prefix="/github-agent", tags=["github-agent"])


def _decode(token: str) -> dict:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


class GithubAgentRequest(BaseModel):
    task: str
    owner: str
    repo: str
    conversation_id: str = ""


@router.post("/run")
async def run_agent(
    body: GithubAgentRequest,
    token: Optional[str] = Query(None),
) -> StreamingResponse:
    """Stream the autonomous GitHub agent as SSE events."""
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    payload = _decode(token)
    github_token = payload.get("github_token")
    if not github_token:
        raise HTTPException(
            status_code=401,
            detail="GitHub not connected. Connect GitHub first.",
        )

    if not body.task.strip():
        raise HTTPException(status_code=400, detail="Task cannot be empty")

    async def event_stream() -> AsyncGenerator[str, None]:
        try:
            async for chunk in run_github_agent(
                task=body.task,
                owner=body.owner,
                repo=body.repo,
                github_token=github_token,
                router=model_router,
                conversation_id=body.conversation_id,
            ):
                yield chunk
        except Exception as e:
            import json, time
            yield f"data: {json.dumps({'type': 'error', 'timestamp': int(time.time()*1000), 'payload': {'message': str(e)}})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
