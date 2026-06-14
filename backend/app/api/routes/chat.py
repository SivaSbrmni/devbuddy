"""Chat endpoint — streaming LLM responses via SSE."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.model_router import LLMRequest, model_router

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    messages: list[dict[str, str]]
    model: str
    system_prompt: str = ""
    max_tokens: int = 4096
    temperature: float = 0.0


def _resolve_provider(model_id: str) -> str:
    """Resolve provider from model id."""
    if model_id.startswith("claude-") or model_id.startswith("anthropic-"):
        return "anthropic"
    return "ollama"


async def _stream_chat(request: ChatRequest):
    """Stream LLM response as SSE events."""
    import structlog
    log = structlog.get_logger()
    
    provider = _resolve_provider(request.model)
    log.info("chat_request", model=request.model, provider=provider, messages_count=len(request.messages))
    
    # Build LLM request
    llm_req = LLMRequest(
        messages=request.messages,
        task_category="planning_draft",  # Default category for chat
        system_prompt=request.system_prompt,
        max_tokens=request.max_tokens,
        temperature=request.temperature,
        model=request.model,
        provider=provider,
    )
    
    try:
        async for delta in model_router._call_provider_stream(llm_req, provider):
            # Send as SSE event
            yield f"data: {delta}\n\n"
        
        # Send done event
        yield "data: [DONE]\n\n"
    except Exception as e:
        import traceback
        error_detail = f"{str(e)}\n{traceback.format_exc()}"
        log.error("chat_error", error=str(e), traceback=traceback.format_exc())
        # Send error event
        yield f"data: [ERROR] {error_detail}\n\n"


@router.post("")
async def chat(request: ChatRequest) -> StreamingResponse:
    """Stream chat response via SSE."""
    return StreamingResponse(
        _stream_chat(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
