"""LLM Gateway — internal API surface for multi-provider inference.

All routes are under /LLM namespace (spec Part 2.1).
Returns 503 until llm_gateway_enabled flag is turned on.

Routes:
  POST /LLM/chat          - Non-streaming chat completion
  POST /LLM/generate      - Text generation
  POST /LLM/stream        - Streaming chat (SSE)
  POST /LLM/embeddings    - Text embeddings
  POST /LLM/context       - Context-aware completion with compression
  POST /LLM/tools         - Tool-calling completion
  POST /LLM/route         - Explicit provider routing
  GET  /LLM/models        - Available models from all providers
  GET  /LLM/health        - Gateway health + provider status
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.feature_flags import feature_flags
from app.core.security import get_current_user
from app.db.session import async_session_factory
from app.models.user import User

router = APIRouter(prefix="/LLM", tags=["llm-gateway"])


async def get_db():
    """FastAPI dependency that yields an async DB session."""
    async with async_session_factory() as db:
        yield db


# ─── Request/Response Schemas ────────────────────────────────────────────────

class LLMChatRequest(BaseModel):
    messages: list[dict[str, str]] = Field(..., description="Chat messages")
    model: Optional[str] = Field(None, description="Model override; null = auto-route")
    task_type: str = Field("planner", description="Task type for routing: planner, coder, debugger, reviewer, docs_summary, embeddings")
    system_prompt: str = ""
    max_tokens: int = 4096
    temperature: float = 0.0
    allow_reserve_tier: bool = Field(False, description="Allow paid reserve tier (last resort only)")


class LLMGenerateRequest(BaseModel):
    prompt: str
    model: Optional[str] = None
    task_type: str = "docs_summary"
    max_tokens: int = 2048
    temperature: float = 0.0


class LLMStreamRequest(BaseModel):
    messages: list[dict[str, str]]
    model: Optional[str] = None
    task_type: str = "coder"
    system_prompt: str = ""
    max_tokens: int = 4096
    temperature: float = 0.0


class LLMEmbeddingsRequest(BaseModel):
    texts: list[str]
    model: Optional[str] = None


class LLMToolsRequest(BaseModel):
    messages: list[dict[str, str]]
    tools: list[dict]
    model: Optional[str] = None
    task_type: str = "coder"
    max_tokens: int = 4096


class LLMRouteRequest(BaseModel):
    task_type: str
    payload_size_tokens: int = 0


class NormalizedLLMResponse(BaseModel):
    """Normalized response shape — every downstream consumer sees this only."""
    text: str
    finish_reason: str = "stop"  # stop, length, tool_call, error
    usage: dict = Field(default_factory=dict)  # {input_tokens, output_tokens}
    provider: str = ""
    model: str = ""
    tokens_saved: dict = Field(default_factory=dict)  # compression savings


class LLMModelsResponse(BaseModel):
    models: list[dict]


class LLMHealthResponse(BaseModel):
    status: str
    providers: dict
    flags: dict


# ─── Route Stubs (503 until Phase 1 wires them) ──────────────────────────────

def _check_gateway() -> None:
    """Gate all /LLM routes behind the llm_gateway_enabled flag."""
    if not feature_flags.is_enabled("llm_gateway_enabled"):
        raise HTTPException(
            status_code=503,
            detail="LLM Gateway is not enabled. Set AEP_FLAG_LLM_GATEWAY_ENABLED=true to activate.",
        )


async def _get_user_gateway(
    user: User,
    db: Any = Depends(get_db),
) -> Any:
    """Create a per-user LLMGateway loaded from the user's encrypted provider config."""
    _check_gateway()
    from app.llm.gateway import LLMGateway
    gateway = LLMGateway(user_id=user.id, db=db)
    await gateway.initialize_for_user()
    return gateway


@router.post("/chat", response_model=NormalizedLLMResponse)
async def llm_chat(
    req: LLMChatRequest,
    user: User = Depends(get_current_user),
    db: Any = Depends(get_db),
) -> NormalizedLLMResponse:
    """Non-streaming chat completion via multi-provider router."""
    gateway = await _get_user_gateway(user, db)
    resp = await gateway.chat(
        messages=req.messages,
        task_type=req.task_type,
        model=req.model,
        system_prompt=req.system_prompt,
        max_tokens=req.max_tokens,
        temperature=req.temperature,
        allow_reserve_tier=req.allow_reserve_tier,
    )
    return NormalizedLLMResponse(
        text=resp.text,
        finish_reason=resp.finish_reason,
        usage=resp.usage,
        provider=resp.provider,
        model=resp.model,
    )


@router.post("/generate", response_model=NormalizedLLMResponse)
async def llm_generate(
    req: LLMGenerateRequest,
    user: User = Depends(get_current_user),
    db: Any = Depends(get_db),
) -> NormalizedLLMResponse:
    """Text generation via multi-provider router."""
    gateway = await _get_user_gateway(user, db)
    resp = await gateway.chat(
        messages=[{"role": "user", "content": req.prompt}],
        task_type=req.task_type,
        model=req.model,
        max_tokens=req.max_tokens,
        temperature=req.temperature,
    )
    return NormalizedLLMResponse(
        text=resp.text,
        finish_reason=resp.finish_reason,
        usage=resp.usage,
        provider=resp.provider,
        model=resp.model,
    )


@router.post("/stream")
async def llm_stream(
    req: LLMStreamRequest,
    user: User = Depends(get_current_user),
    db: Any = Depends(get_db),
):
    """Streaming chat via SSE through multi-provider router."""
    from fastapi.responses import StreamingResponse
    gateway = await _get_user_gateway(user, db)

    async def event_stream():
        async for chunk in gateway.stream(
            messages=req.messages,
            task_type=req.task_type,
            model=req.model,
            system_prompt=req.system_prompt,
            max_tokens=req.max_tokens,
            temperature=req.temperature,
        ):
            yield f"data: {chunk}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/embeddings")
async def llm_embeddings(
    req: LLMEmbeddingsRequest,
    user: User = Depends(get_current_user),
    db: Any = Depends(get_db),
):
    """Text embeddings via the user's configured embedding providers."""
    gateway = await _get_user_gateway(user, db)
    embeddings = await gateway.embeddings(req.texts, req.model)
    return {"embeddings": embeddings, "count": len(embeddings)}


@router.post("/context", response_model=NormalizedLLMResponse)
async def llm_context(
    req: LLMChatRequest,
    user: User = Depends(get_current_user),
    db: Any = Depends(get_db),
) -> NormalizedLLMResponse:
    """Context-aware completion with automatic compression pipeline."""
    gateway = await _get_user_gateway(user, db)
    from app.llm.compression import compress_payload
    # Compress the messages before sending
    compressed = compress_payload({"messages": req.messages, "system_prompt": req.system_prompt})
    resp = await gateway.chat(
        messages=compressed["messages"],
        task_type=req.task_type,
        system_prompt=compressed.get("system_prompt", ""),
        max_tokens=req.max_tokens,
        temperature=req.temperature,
    )
    return NormalizedLLMResponse(
        text=resp.text,
        finish_reason=resp.finish_reason,
        usage=resp.usage,
        provider=resp.provider,
        model=resp.model,
        tokens_saved=compressed.get("tokens_saved", {}),
    )


@router.post("/tools", response_model=NormalizedLLMResponse)
async def llm_tools(
    req: LLMToolsRequest,
    user: User = Depends(get_current_user),
    db: Any = Depends(get_db),
) -> NormalizedLLMResponse:
    """Tool-calling completion via multi-provider router."""
    gateway = await _get_user_gateway(user, db)
    # Append tools as a system instruction for providers that don't natively support tool calling
    tools_desc = str(req.tools)
    resp = await gateway.chat(
        messages=req.messages,
        task_type=req.task_type,
        system_prompt=f"Available tools: {tools_desc}",
        max_tokens=req.max_tokens,
    )
    return NormalizedLLMResponse(
        text=resp.text,
        finish_reason=resp.finish_reason,
        usage=resp.usage,
        provider=resp.provider,
        model=resp.model,
    )


@router.post("/route")
async def llm_route(
    req: LLMRouteRequest,
    user: User = Depends(get_current_user),
    db: Any = Depends(get_db),
) -> dict:
    """Preview which provider the router would select for a given task type."""
    gateway = await _get_user_gateway(user, db)
    cascade = gateway.get_cascade(req.task_type)
    return {"task_type": req.task_type, "cascade": cascade}


@router.get("/models", response_model=LLMModelsResponse)
async def llm_models(
    user: User = Depends(get_current_user),
    db: Any = Depends(get_db),
) -> LLMModelsResponse:
    """List available models from all configured providers."""
    gateway = await _get_user_gateway(user, db)
    models = await gateway.list_models()
    return LLMModelsResponse(models=models)


@router.get("/health", response_model=LLMHealthResponse)
async def llm_health() -> LLMHealthResponse:
    """Gateway health check with per-provider status."""
    flags = feature_flags.get_all_flags()
    if not flags.get("llm_gateway_enabled"):
        return LLMHealthResponse(
            status="disabled",
            providers={},
            flags=flags,
        )
    from app.llm.gateway import llm_gateway
    if not llm_gateway._initialized:
        llm_gateway.initialize()
    providers = await llm_gateway.health_check()
    return LLMHealthResponse(
        status="healthy" if all(p["ok"] for p in providers.values()) else "degraded",
        providers=providers,
        flags=flags,
    )
