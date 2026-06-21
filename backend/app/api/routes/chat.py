"""Chat endpoint — streaming LLM responses via SSE.

Uses the user's configured LLM providers. Falls back to legacy UserSettings
API keys (anthropic/ollama/llama) when no user_llm_providers are configured.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select

from app.core.config import settings
from app.core.crypto import crypto, encrypt_value
from app.core.security import get_current_user
from app.db.session import async_session_factory
from app.llm.gateway import LLMGateway
from app.llm.providers.user_provider import UserProviderAdapter
from app.models.llm_provider import UserLLMProvider
from app.models.user import User
from app.models.user_settings import UserSettings

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    messages: list[dict[str, str]]
    model: str
    system_prompt: str = ""
    max_tokens: int = 4096
    temperature: float = 0.0


_LEGACY_PROVIDER_DEFAULTS = {
    "anthropic": {
        "provider_type": "anthropic",
        "base_url": "https://api.anthropic.com/v1",
        "default_model": "claude-3-5-sonnet-20241022",
    },
    "llama": {
        "provider_type": "openai-compatible",
        "base_url": "https://api.llama.com/v1",
        "default_model": "llama-4-scout-17b-16e-instruct",
    },
    "ollama": {
        "provider_type": "ollama",
        "base_url": "https://ollama.com",
        "default_model": "qwen3-coder:480b",
    },
}


def _make_legacy_provider_record(user: User, name: str, key: str, base_url: str) -> UserLLMProvider:
    """Create an in-memory UserLLMProvider record from legacy UserSettings data."""
    defaults = _LEGACY_PROVIDER_DEFAULTS[name]
    return UserLLMProvider(
        user_id=user.id,
        name=name,
        provider_type=defaults["provider_type"],
        base_url=base_url,
        api_key_encrypted=encrypt_value(key) if key else "",
        default_model=defaults["default_model"],
        available_models=[defaults["default_model"]],
        headers={},
        supports_streaming=True,
        supports_tools=True,
        supports_vision=False,
        context_size=8192,
        max_tokens=4096,
        cost_per_1k_input=0.0,
        cost_per_1k_output=0.0,
        priority=100,
        is_active=True,
        is_default=False,
    )


async def _stream_chat(request: ChatRequest, user: User):
    """Stream LLM response as SSE events using user-configured providers."""
    import structlog
    import traceback

    log = structlog.get_logger()
    log.info("chat_request", model=request.model, user_id=str(user.id), messages_count=len(request.messages))

    async with async_session_factory() as db:
        gateway = LLMGateway(user_id=user.id, db=db)
        await gateway.initialize_for_user()

        # Fallback to legacy UserSettings API keys if no user_llm_providers configured
        if not gateway.providers:
            log.info("chat_no_user_providers", user_id=str(user.id), email=user.email)
            stmt = select(UserSettings).where(UserSettings.email == user.email)
            result = await db.execute(stmt)
            row = result.scalar_one_or_none()
            if row:
                decrypted = crypto.decrypt_dict(row.api_keys)
                for name, cfg in decrypted.items():
                    if name not in _LEGACY_PROVIDER_DEFAULTS:
                        continue

                    key = cfg.get("key", "")
                    defaults = _LEGACY_PROVIDER_DEFAULTS[name]
                    base_url = cfg.get("base_url") or defaults["base_url"]
                    if name == "ollama":
                        base_url = base_url or settings.OLLAMA_API_BASE
                    elif name == "llama":
                        base_url = base_url or settings.LLAMA_API_BASE
                    elif name == "anthropic":
                        base_url = base_url or "https://api.anthropic.com/v1"

                    if not key:
                        # Also allow global env keys for legacy providers
                        if name == "anthropic":
                            key = settings.ANTHROPIC_API_KEY or ""
                        elif name == "ollama":
                            key = settings.OLLAMA_API_KEY or ""
                        elif name == "llama":
                            key = settings.LLAMA_API_KEY or ""

                    if not key:
                        continue

                    record = _make_legacy_provider_record(user, name, key, base_url)
                    adapter = UserProviderAdapter(record)
                    gateway.providers[name] = adapter
                    gateway._default_cascade.append((name, defaults["default_model"]))
                    log.info("chat_legacy_provider_loaded", user_id=str(user.id), name=name)

        log.info("chat_providers_loaded", user_id=str(user.id), providers=list(gateway.providers.keys()), model=request.model)
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
