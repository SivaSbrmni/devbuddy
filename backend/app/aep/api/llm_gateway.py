"""
``/LLM`` gateway — Phase 0 stub.

Per the AEP spec §2.2 every model invocation must flow through a
unified internal gateway mounted at ``/LLM``. In Phase 0 every route
is wired but returns a structured **503** envelope so callers can
already integrate against the contract — Phase 1 replaces the bodies
with real Ollama proxying.

The gateway is mounted at the application root (NOT under
``/api/v1``) to match the spec literally.

Endpoints (all 503 in Phase 0):

    POST /LLM/generate    — text generation
    POST /LLM/chat        — chat completion
    POST /LLM/embed       — embeddings
    POST /LLM/route       — model routing by task type
    GET  /LLM/models      — list available models
    GET  /LLM/health      — gateway health probe

Authentication is enforced via the existing Supabase JWT scheme. The
gateway never exposes raw Ollama URLs to the caller.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, Field

from app.core.security import get_current_user
from app.aep.feature_flags import get_feature_flag_service

router = APIRouter(prefix="/LLM", tags=["aep-llm-gateway"])

PHASE = "phase_0"
SERVICE_UNAVAILABLE_MESSAGE = (
    "AEP LLM gateway is not enabled. Set the feature flag "
    "`llm_gateway_enabled` to true (Phase 1) to activate this endpoint."
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
    context: dict[str, Any] = Field(default_factory=dict)


class GatewayErrorEnvelope(BaseModel):
    """Structured 503 envelope used by every gateway endpoint in Phase 0."""

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
    # No DB session is available here in Phase 0 — env-var fallback and
    # global defaults are sufficient.
    return await ff.is_enabled("llm_gateway_enabled")


def _service_unavailable(response: Response) -> dict[str, Any]:
    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    response.headers["X-AEP-Phase"] = PHASE
    response.headers["X-AEP-Flag"] = "llm_gateway_enabled"
    return _disabled_envelope()


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/health")
async def gateway_health(response: Response) -> dict[str, Any]:
    """Lightweight readiness probe for the gateway.

    Authentication is **not** required so external uptime monitors can
    poll it. The probe never reaches Ollama — it only reflects the
    flag state.
    """
    enabled = await _gateway_enabled()
    if not enabled:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        response.headers["X-AEP-Phase"] = PHASE
        return {
            "status": "disabled",
            "phase": PHASE,
            "flag": "llm_gateway_enabled",
            "message": SERVICE_UNAVAILABLE_MESSAGE,
        }
    return {"status": "ok", "phase": PHASE}


@router.post("/generate")
async def generate(
    body: GenerateRequest,
    response: Response,
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    if not await _gateway_enabled():
        return _service_unavailable(response)
    # Phase 1 will replace this body with a real Ollama call.
    return _service_unavailable(response)


@router.post("/chat")
async def chat(
    body: ChatRequest,
    response: Response,
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    if not await _gateway_enabled():
        return _service_unavailable(response)
    return _service_unavailable(response)


@router.post("/embed")
async def embed(
    body: EmbedRequest,
    response: Response,
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    if not await _gateway_enabled():
        return _service_unavailable(response)
    return _service_unavailable(response)


@router.post("/route")
async def route(
    body: RouteRequest,
    response: Response,
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    if not await _gateway_enabled():
        return _service_unavailable(response)
    return _service_unavailable(response)


@router.get("/models")
async def list_models(
    response: Response,
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    if not await _gateway_enabled():
        return _service_unavailable(response)
    return _service_unavailable(response)


__all__ = ["router"]
