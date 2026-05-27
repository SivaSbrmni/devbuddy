"""Configuration for the AEP LLM subsystem.

All values are sourced from environment variables. Defaults are chosen
so that:

* on a fresh laptop with a local ``ollama serve`` running on
  ``127.0.0.1:11434`` everything works without configuration;
* on the GCP VM where ``gemma4:31b-cloud`` is reached via an Ollama
  Cloud sidecar, the operator only needs to set
  ``OLLAMA_CLOUD_API_KEY`` (and, if not co-located, ``AEP_OLLAMA_BASE_URL``).

The class is intentionally **separate** from
``app.core.config.Settings`` to keep the AEP layer self-contained — no
existing field on ``Settings`` is altered. ``OLLAMA_URL`` from the
existing settings is used as a fallback when ``AEP_OLLAMA_BASE_URL``
is not explicitly set so the two systems stay in sync on existing
deployments.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

from app.core.config import settings as _core_settings


@dataclass(frozen=True)
class AepLlmConfig:
    """Resolved Ollama runtime configuration for the AEP gateway."""

    base_url: str
    api_key: Optional[str]
    default_model: str
    embedding_model: str
    request_timeout_seconds: float
    connect_timeout_seconds: float
    max_retries: int
    backoff_initial_seconds: float
    backoff_max_seconds: float
    user_agent: str
    extra_headers: dict[str, str] = field(default_factory=dict)

    # ───────────────────────────────────────────────────────────────────
    # Derived helpers
    # ───────────────────────────────────────────────────────────────────

    @property
    def is_cloud(self) -> bool:
        """``True`` when an API key is configured (Ollama Cloud mode)."""
        return bool(self.api_key)

    def auth_headers(self) -> dict[str, str]:
        """Headers attached to every upstream request."""
        headers: dict[str, str] = {
            "Accept": "application/json",
            "User-Agent": self.user_agent,
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        headers.update(self.extra_headers)
        return headers


# ─────────────────────────────────────────────────────────────────────────────
# Loader
# ─────────────────────────────────────────────────────────────────────────────


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_str(name: str, default: str) -> str:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return raw


def _load() -> AepLlmConfig:
    # Prefer AEP-specific override; fall back to the legacy core setting.
    base_url = (
        os.getenv("AEP_OLLAMA_BASE_URL")
        or getattr(_core_settings, "OLLAMA_URL", None)
        or "http://127.0.0.1:11434"
    )
    base_url = base_url.rstrip("/")

    api_key = os.getenv("OLLAMA_CLOUD_API_KEY") or os.getenv("AEP_OLLAMA_API_KEY")
    if api_key is not None and api_key.strip() == "":
        api_key = None

    return AepLlmConfig(
        base_url=base_url,
        api_key=api_key,
        default_model=_env_str("AEP_DEFAULT_MODEL", "gemma4:31b-cloud"),
        embedding_model=_env_str("AEP_EMBEDDING_MODEL", "nomic-embed-text"),
        request_timeout_seconds=_env_float("AEP_OLLAMA_REQUEST_TIMEOUT", 120.0),
        connect_timeout_seconds=_env_float("AEP_OLLAMA_CONNECT_TIMEOUT", 10.0),
        max_retries=_env_int("AEP_OLLAMA_MAX_RETRIES", 2),
        backoff_initial_seconds=_env_float("AEP_OLLAMA_BACKOFF_INITIAL", 0.5),
        backoff_max_seconds=_env_float("AEP_OLLAMA_BACKOFF_MAX", 8.0),
        user_agent=_env_str("AEP_OLLAMA_USER_AGENT", "devbuddy-aep/1"),
    )


_cached: Optional[AepLlmConfig] = None


def get_aep_llm_config(*, refresh: bool = False) -> AepLlmConfig:
    """Return the process-wide :class:`AepLlmConfig` singleton.

    Tests can pass ``refresh=True`` to pick up newly set env vars.
    """
    global _cached
    if refresh or _cached is None:
        _cached = _load()
    return _cached


def reset_aep_llm_config() -> None:
    """Test hook to clear the cached config."""
    global _cached
    _cached = None


__all__ = ["AepLlmConfig", "get_aep_llm_config", "reset_aep_llm_config"]
