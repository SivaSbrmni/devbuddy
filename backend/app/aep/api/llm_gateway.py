"""
``/LLM`` gateway — Phase 1 implementation.

Per the AEP spec §2.2 every model invocation must flow through a
unified internal gateway mounted at ``/LLM``. Phase 0 shipped the
contract with every route returning a structured ``503`` envelope so
callers could already integrate against the surface. Phase 1 wires
the route bodies to a real Ollama backend (local or Ollama Cloud) via
:class:`app.aep.llm.LlmGatewayService` and keeps the same 503 envelope
as a fail-safe whenever the ``llm_gateway_enabled`` feature flag is
**off** — so the rollout remains gated end-to-end.

The gateway is mounted at the application root (NOT under
``/api/v1``) to match the spec literally.

Endpoints:

    POST /LLM/generate    — text generation (supports stream=true SSE)
    POST /LLM/chat        — chat completion (supports stream=true SSE)
    POST /LLM/embed       — embeddings
    POST /LLM/route       — model routing by task type
    GET  /LLM/models      — list available models
    GET  /LLM/health      — gateway health probe (no auth)

Authentication is enforced via the existing Supabase JWT scheme on
every endpoint except ``/LLM/health``. The gateway never exposes raw
Ollama URLs to the caller.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Literal, Optional

from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.aep.feature_flags import get_feature_flag_service
from app.aep.llm.errors import LlmGatewayError
from app.aep.llm.gateway import get_llm_gateway_service
from app.core.security import get_current_user

router = APIRouter(prefix="/LLM", tags=["aep-llm-gateway"])

PHASE = "phase_1"
SERVICE_UNAVAILABLE_MESSAGE = (
    "AEP LLM gateway is not enabled. Set the feature flag "
    "`llm_gateway_enabled` to true to activate this endpoint."
)


# ─────────────────────────────────────────────────────────────────────────────
# Request / response schemas
# ─────────────────────────────────────────────────────────────────────────────


class GenerateRequest(BaseModel):
    prompt: str
    model: Optional[str] = None
    temperature: float = 0.2
    max_tokens: int = 512
    stream: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    name: Optional[str] = None


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    model: Optional[str] = None
    temperature: float = 0.2
    max_tokens: int = 512
    stream: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class EmbedRequest(BaseModel):
    input: str | list[str]
    model: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RouteRequest(BaseModel):
    """Routing hint to choose a model for a given task type."""

    task_type: Literal[
        "plan",
        "code",
        "debug",
        "test",
        "review",
        "security_audit",
        "documentation",
        "devops",
        "embedding",
        "generic",
    ]
    model_override: Optional[str] = None
    context: dict[str, Any] = Field(default_factory=dict)


class GatewayErrorEnvelope(BaseModel):
    """Structured 503 envelope returned when the gateway flag is off."""

    error: Literal["service_unavailable"] = "service_unavailable"
    phase: str = PHASE
    message: str = SERVICE_UNAVAILABLE_MESSAGE
    flag: str = "llm_gateway_enabled"
    timestamp: str


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _disabled_envelope() -> dict[str, Any]:
    return GatewayErrorEnvelope(
        timestamp=datetime.now(timezone.utc).isoformat()
    ).model_dump()


async def _gateway_enabled() -> bool:
    ff = get_feature_flag_service()
    # The gateway flag must be resolvable without a DB session — env
    # var fallback and global defaults are sufficient for cold start.
    return await ff.is_enabled("llm_gateway_enabled")


def _service_unavailable(response: Response) -> dict[str, Any]:
    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    response.headers["X-AEP-Phase"] = PHASE
    response.headers["X-AEP-Flag"] = "llm_gateway_enabled"
    return _disabled_envelope()


def _upstream_envelope(exc: LlmGatewayError) -> dict[str, Any]:
    env = exc.to_envelope()
    env["phase"] = PHASE
    env["flag"] = "llm_gateway_enabled"
    env["timestamp"] = datetime.now(timezone.utc).isoformat()
    return env


def _attach_aep_headers(response: Response) -> None:
    response.headers["X-AEP-Phase"] = PHASE
    response.headers["X-AEP-Flag"] = "llm_gateway_enabled"


def _tenant_id(user: dict) -> Optional[str]:
    payload = user.get("payload") or {}
    return payload.get("tenant_id") or payload.get("tenant") or None


def _normalize_embed_inputs(inp: str | list[str]) -> list[str]:
    if isinstance(inp, str):
        return [inp]
    return list(inp)


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/health")
async def gateway_health(response: Response) -> dict[str, Any]:
    """Lightweight readiness probe for the gateway.

    Authentication is **not** required so external uptime monitors can
    poll it. When the flag is off, returns 503 immediately. When on,
    probes the upstream Ollama instance.
    """
    enabled = await _gateway_enabled()
    if not enabled:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        _attach_aep_headers(response)
        return {
            "status": "disabled",
            "phase": PHASE,
            "flag": "llm_gateway_enabled",
            "message": SERVICE_UNAVAILABLE_MESSAGE,
        }
    service = get_llm_gateway_service()
    try:
        upstream = await service.health()
    except LlmGatewayError as exc:
        response.status_code = exc.http_status
        _attach_aep_headers(response)
        return _upstream_envelope(exc)
    _attach_aep_headers(response)
    return {"phase": PHASE, **upstream}


@router.post("/generate")
async def generate(
    body: GenerateRequest,
    response: Response,
    user: dict = Depends(get_current_user),
):
    if not await _gateway_enabled():
        return _service_unavailable(response)

    service = get_llm_gateway_service()
    tenant_id = _tenant_id(user)

    if body.stream:
        async def iterator() -> AsyncIterator[bytes]:
            try:
                async for chunk in service.generate_stream(
                    prompt=body.prompt,
                    model=body.model,
                    temperature=body.temperature,
                    max_tokens=body.max_tokens,
                    tenant_id=tenant_id,
                ):
                    yield _sse_event(chunk)
            except LlmGatewayError as exc:
                yield _sse_event(_upstream_envelope(exc), event="error")

        _attach_aep_headers(response)
        return StreamingResponse(
            iterator(),
            media_type="text/event-stream",
            headers={"X-AEP-Phase": PHASE, "X-AEP-Flag": "llm_gateway_enabled"},
        )

    try:
        result = await service.generate(
            prompt=body.prompt,
            model=body.model,
            temperature=body.temperature,
            max_tokens=body.max_tokens,
            metadata=body.metadata,
            tenant_id=tenant_id,
        )
    except LlmGatewayError as exc:
        response.status_code = exc.http_status
        _attach_aep_headers(response)
        return _upstream_envelope(exc)
    _attach_aep_headers(response)
    return result


@router.post("/chat")
async def chat(
    body: ChatRequest,
    response: Response,
    user: dict = Depends(get_current_user),
):
    if not await _gateway_enabled():
        return _service_unavailable(response)

    service = get_llm_gateway_service()
    tenant_id = _tenant_id(user)
    messages = [m.model_dump(exclude_none=True) for m in body.messages]

    if body.stream:
        async def iterator() -> AsyncIterator[bytes]:
            try:
                async for chunk in service.chat_stream(
                    messages=messages,
                    model=body.model,
                    temperature=body.temperature,
                    max_tokens=body.max_tokens,
                    tenant_id=tenant_id,
                ):
                    yield _sse_event(chunk)
            except LlmGatewayError as exc:
                yield _sse_event(_upstream_envelope(exc), event="error")

        _attach_aep_headers(response)
        return StreamingResponse(
            iterator(),
            media_type="text/event-stream",
            headers={"X-AEP-Phase": PHASE, "X-AEP-Flag": "llm_gateway_enabled"},
        )

    try:
        result = await service.chat(
            messages=messages,
            model=body.model,
            temperature=body.temperature,
            max_tokens=body.max_tokens,
            metadata=body.metadata,
            tenant_id=tenant_id,
        )
    except LlmGatewayError as exc:
        response.status_code = exc.http_status
        _attach_aep_headers(response)
        return _upstream_envelope(exc)
    _attach_aep_headers(response)
    return result


@router.post("/embed")
async def embed(
    body: EmbedRequest,
    response: Response,
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    if not await _gateway_enabled():
        return _service_unavailable(response)

    service = get_llm_gateway_service()
    inputs = _normalize_embed_inputs(body.input)
    try:
        result = await service.embed(
            inputs=inputs,
            model=body.model,
            metadata=body.metadata,
            tenant_id=_tenant_id(user),
        )
    except LlmGatewayError as exc:
        response.status_code = exc.http_status
        _attach_aep_headers(response)
        return _upstream_envelope(exc)
    _attach_aep_headers(response)
    return result


@router.post("/route")
async def route(
    body: RouteRequest,
    response: Response,
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    if not await _gateway_enabled():
        return _service_unavailable(response)
    service = get_llm_gateway_service()
    _attach_aep_headers(response)
    return service.route(body.task_type, override=body.model_override)


@router.get("/models")
async def list_models(
    response: Response,
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    if not await _gateway_enabled():
        return _service_unavailable(response)
    service = get_llm_gateway_service()
    try:
        result = await service.list_models()
    except LlmGatewayError as exc:
        response.status_code = exc.http_status
        _attach_aep_headers(response)
        return _upstream_envelope(exc)
    _attach_aep_headers(response)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# SSE helpers
# ─────────────────────────────────────────────────────────────────────────────


def _sse_event(payload: dict[str, Any], *, event: Optional[str] = None) -> bytes:
    data = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    if event:
        return f"event: {event}\ndata: {data}\n\n".encode("utf-8")
    return f"data: {data}\n\n".encode("utf-8")


__all__ = ["router"]
