"""Cloud Agent API — GitHub Actions execution engine endpoint."""

from __future__ import annotations

from typing import Optional, AsyncGenerator

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from jose import jwt
from pydantic import BaseModel

from app.core.config import settings
from app.agents.cloud_runner import run_cloud_agent

router = APIRouter(prefix="/cloud-agent", tags=["cloud-agent"])


def _decode(token: str) -> dict:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


class CloudAgentRequest(BaseModel):
    task: str
    owner: str
    repo: str
    conversation_id: str = ""


@router.post("/run")
async def run_agent(
    request: Request,
    body: CloudAgentRequest,
    token: Optional[str] = Query(None),
) -> StreamingResponse:
    """Dispatch an ephemeral GitHub Actions job and stream its lifecycle as SSE."""
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

    # Derive callback URL from request
    base_url = str(request.base_url).rstrip("/")
    devbuddy_url = f"{base_url}/api/v1"

    async def event_stream() -> AsyncGenerator[str, None]:
        try:
            async for chunk in run_cloud_agent(
                task=body.task,
                owner=body.owner,
                repo=body.repo,
                github_token=github_token,
                devbuddy_url=devbuddy_url,
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


@router.get("/status/{run_id}")
async def get_run_status(
    run_id: int,
    owner: str,
    repo: str,
    token: Optional[str] = Query(None),
) -> dict:
    """Get live status of a GitHub Actions run."""
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = _decode(token)
    github_token = payload.get("github_token")
    if not github_token:
        raise HTTPException(status_code=401, detail="GitHub not connected")

    import httpx
    GITHUB_API = "https://api.github.com"
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{GITHUB_API}/repos/{owner}/{repo}/actions/runs/{run_id}",
            headers={
                "Authorization": f"Bearer {github_token}",
                "Accept": "application/vnd.github+json",
            },
        )
        if not resp.is_success:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        data = resp.json()
        return {
            "run_id": run_id,
            "status": data.get("status"),
            "conclusion": data.get("conclusion"),
            "html_url": data.get("html_url"),
            "created_at": data.get("created_at"),
            "updated_at": data.get("updated_at"),
        }
