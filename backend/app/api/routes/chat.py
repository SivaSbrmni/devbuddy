"""Chat endpoint — streaming LLM responses via SSE.

Uses the user's configured LLM providers instead of the legacy model router.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.security import get_current_user
from app.db.session import async_session_factory
from app.llm.gateway import LLMGateway
from app.models.user import User

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    messages: list[dict[str, str]]
    model: str
    system_prompt: str = ""
    max_tokens: int = 4096
    temperature: float = 0.0


async def _stream_chat(request: ChatRequest, user: User):
    """Stream LLM response as SSE events using user-configured providers."""
    import structlog
    import traceback

    log = structlog.get_logger()
    log.info("chat_request", model=request.model, user_id=str(user.id), messages_count=len(request.messages))

    async with async_session_factory() as db:
        gateway = LLMGateway(user_id=user.id, db=db)
        await gateway.initialize_for_user()

        if not gateway.providers:
            log.warning("chat_no_providers", user_id=str(user.id))
            yield "data: No LLM providers configured. Add a provider in Settings → LLM Providers.\n\n"
            yield "data: [DONE]\n\n"
            return

        try:
            yielded_any = False
            async for delta in gateway.stream(
                messages=request.messages,
                task_type="coder",
                model=request.model,
                system_prompt=request.system_prompt,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
            ):
                if delta:
                    yielded_any = True
                yield f"data: {delta}\n\n"

            if not yielded_any:
                yield "data: All LLM providers failed. Check your provider settings and API keys.\n\n"

            yield "data: [DONE]\n\n"
        except Exception as e:
            error_detail = f"{str(e)}\n{traceback.format_exc()}"
            log.error("chat_error", error=str(e), traceback=traceback.format_exc())
            yield f"data: [ERROR] {error_detail}\n\n"


@router.post("")
async def chat(
    request: ChatRequest,
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    """Stream chat response via SSE."""
    return StreamingResponse(
        _stream_chat(request, user),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
