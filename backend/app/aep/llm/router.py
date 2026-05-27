"""Task-type → model routing per spec §2.5.

The routing table is intentionally data-driven so operators can tune
model selection without touching code by setting environment variables
of the form::

    AEP_MODEL_FOR_<TASK_TYPE>=<model-name>

For example::

    AEP_MODEL_FOR_DOCUMENTATION=mistral:7b
    AEP_MODEL_FOR_CODE=gemma4:31b-cloud

The base table follows the spec defaults so an out-of-the-box install
matches the contract.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping, Optional

from app.aep.llm.config import AepLlmConfig, get_aep_llm_config


# Spec §2.5 — default task-type → model mapping.
SPEC_DEFAULT_MAPPING: dict[str, str] = {
    "plan": "gemma4:31b-cloud",
    "code": "gemma4:31b-cloud",
    "debug": "gemma4:31b-cloud",
    "test": "gemma4:31b-cloud",
    "review": "gemma4:31b-cloud",
    "security_audit": "gemma4:31b-cloud",
    "documentation": "mistral:7b",
    "devops": "gemma4:31b-cloud",
    "embedding": "nomic-embed-text",
    "generic": "gemma4:31b-cloud",
}


# Spec §2.4 — fallback models when the primary is unavailable.
SPEC_FALLBACK_MAPPING: dict[str, str] = {
    "code": "deepseek-coder",
    "test": "qwen2.5-coder",
    "documentation": "mistral:7b",
}


@dataclass(frozen=True)
class RouteDecision:
    task_type: str
    primary: str
    fallback: Optional[str]
    source: str  # "override" | "env" | "config_default" | "spec_default"


class ModelRouter:
    """Resolves a model name for an inference request."""

    def __init__(
        self,
        *,
        config: Optional[AepLlmConfig] = None,
        mapping: Optional[Mapping[str, str]] = None,
        fallback_mapping: Optional[Mapping[str, str]] = None,
    ) -> None:
        self._config = config or get_aep_llm_config()
        self._mapping: dict[str, str] = dict(mapping or SPEC_DEFAULT_MAPPING)
        self._fallback: dict[str, str] = dict(fallback_mapping or SPEC_FALLBACK_MAPPING)

    # ─────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────

    def known_task_types(self) -> list[str]:
        return sorted(self._mapping.keys())

    def route(
        self,
        task_type: str,
        *,
        override: Optional[str] = None,
    ) -> RouteDecision:
        """Pick a model for ``task_type`` honoring overrides.

        Resolution order:

        1. Explicit ``override`` argument (caller specified ``model`` in
           the request body).
        2. ``AEP_MODEL_FOR_<TASK_TYPE>`` environment variable.
        3. Static spec table (:data:`SPEC_DEFAULT_MAPPING`).
        4. Configured ``default_model`` from :class:`AepLlmConfig`.
        """
        normalized = task_type.lower().strip()

        if override:
            return RouteDecision(
                task_type=normalized,
                primary=override,
                fallback=self._fallback.get(normalized),
                source="override",
            )

        env_key = f"AEP_MODEL_FOR_{normalized.upper()}"
        env_val = os.getenv(env_key)
        if env_val:
            return RouteDecision(
                task_type=normalized,
                primary=env_val,
                fallback=self._fallback.get(normalized),
                source="env",
            )

        primary = self._mapping.get(normalized)
        if primary:
            return RouteDecision(
                task_type=normalized,
                primary=primary,
                fallback=self._fallback.get(normalized),
                source="spec_default",
            )

        return RouteDecision(
            task_type=normalized,
            primary=self._config.default_model,
            fallback=None,
            source="config_default",
        )

    def as_mapping(self) -> dict[str, str]:
        """Snapshot of the routing table (for diagnostics / admin UI)."""
        return dict(self._mapping)


# ─────────────────────────────────────────────────────────────────────────────
# Singleton
# ─────────────────────────────────────────────────────────────────────────────


_router: Optional[ModelRouter] = None


def get_model_router(*, refresh: bool = False) -> ModelRouter:
    global _router
    if refresh or _router is None:
        _router = ModelRouter()
    return _router


def reset_model_router() -> None:
    global _router
    _router = None


__all__ = [
    "ModelRouter",
    "RouteDecision",
    "SPEC_DEFAULT_MAPPING",
    "SPEC_FALLBACK_MAPPING",
    "get_model_router",
    "reset_model_router",
]
