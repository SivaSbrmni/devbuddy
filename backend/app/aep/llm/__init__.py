"""AEP LLM subsystem — Phase 1.

This package contains the production implementation of the ``/LLM``
gateway introduced as a stub in Phase 0.

Modules
-------
* :mod:`config`    — :class:`AepLlmConfig`, environment-driven settings.
* :mod:`errors`    — structured exception hierarchy.
* :mod:`router`    — task-type → model routing table.
* :mod:`ollama_client` — async HTTP client for Ollama (local **or** Ollama
  Cloud) speaking the ``/api/{generate,chat,embed,tags}`` surface.
* :mod:`gateway`   — high-level service used by the FastAPI routes.

Phase 1 introduces *real* LLM inference behind the
``llm_gateway_enabled`` feature flag. When the flag is off (the default
on a fresh install) every gateway endpoint continues to return the
Phase 0 ``503`` envelope, so the rollout is gated end-to-end.

The package is **purely additive**: no Phase 0 surface is modified.
"""

from app.aep.llm.config import AepLlmConfig, get_aep_llm_config
from app.aep.llm.errors import (
    LlmGatewayError,
    UpstreamUnavailable,
    UpstreamTimeout,
    UpstreamHttpError,
    ModelNotFound,
)
from app.aep.llm.gateway import LlmGatewayService, get_llm_gateway_service
from app.aep.llm.ollama_client import OllamaClient
from app.aep.llm.router import ModelRouter, get_model_router

__all__ = [
    "AepLlmConfig",
    "get_aep_llm_config",
    "LlmGatewayError",
    "UpstreamUnavailable",
    "UpstreamTimeout",
    "UpstreamHttpError",
    "ModelNotFound",
    "LlmGatewayService",
    "get_llm_gateway_service",
    "OllamaClient",
    "ModelRouter",
    "get_model_router",
]
