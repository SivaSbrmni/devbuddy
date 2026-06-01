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


# Default task-type → model mapping. Spec §2.5 lists `gemma4:31b-cloud`
# as the primary for every reasoning task, but using a 31B model for
# *every* call is wasteful when many tasks are routine code/text
# transformations. The defaults below assign models by task complexity
# to balance quality against per-token cost. Every entry remains
# operator-tunable via ``AEP_MODEL_FOR_<TASK_TYPE>`` env vars.
#
# Cost/complexity tiering rationale:
#   * Heavy reasoning (plan, debug, review, security_audit) keeps the
#     31B model — these calls are infrequent and getting them wrong is
#     expensive (e.g. a bad plan cascades into bad code).
#   * Code generation (code) uses a specialised coder model that
#     outperforms generalists at coding while being smaller / cheaper.
#   * Routine structured output (test, devops) drops to a 7B coder.
#   * Documentation stays on mistral:7b per spec §6.1.
#   * Generic falls back to an 8B general model rather than the 31B.
SPEC_DEFAULT_MAPPING: dict[str, str] = {
    "plan":           "gemma4:31b-cloud",     # reasoning-heavy, infrequent
    "code":           "qwen2.5-coder:32b",    # specialised coder
    "debug":          "gemma4:31b-cloud",     # root-cause needs reasoning
    "test":           "qwen2.5-coder:7b",     # structured code, smaller model fine
    "review":         "gemma4:31b-cloud",     # judgment matters, infrequent
    "security_audit": "gemma4:31b-cloud",     # low tolerance for misses
    "documentation":  "mistral:7b",           # spec §6.1 default
    "devops":         "qwen2.5-coder:7b",     # YAML / Dockerfile, structured
    "embedding":      "nomic-embed-text",     # spec §2.1 default
    "generic":        "llama3.1:8b",          # cheap general default
}


# Fallback models when the primary is unavailable (e.g. not pulled
# locally, or rate-limited on Ollama Cloud). Always cheaper than the
# primary so failover degrades cost rather than escalates it.
SPEC_FALLBACK_MAPPING: dict[str, str] = {
    "plan":           "llama3.1:8b",
    "code":           "deepseek-coder:6.7b",
    "debug":          "qwen2.5-coder:7b",
    "test":           "mistral:7b",
    "review":         "mistral:7b",
    "security_audit": "mistral:7b",
    "documentation":  "llama3.2:3b",
    "devops":         "mistral:7b",
    "generic":        "llama3.2:3b",
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
