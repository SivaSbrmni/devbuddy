"""Feature flag service — runtime-evaluable, per-tenant flags.

All autonomous engine features are gated behind flags. Flags default to off,
ensuring backward compatibility. Flags can be toggled via:
1. Environment variables (global defaults)
2. Database override (per-tenant)
3. Admin API endpoint

This module is the single source of truth for feature gating.
"""

from __future__ import annotations

import os
from typing import Any, Optional

import structlog

log = structlog.get_logger()

# ─── Flag Definitions ────────────────────────────────────────────────────────

# Master kill switch and individual feature flags from the spec (Part 1)
DEFAULT_FLAGS: dict[str, bool] = {
    "autonomous_engine_enabled": False,       # master kill switch
    "llm_gateway_enabled": False,
    "github_actions_runtime_enabled": False,
    "agent_planner_enabled": False,
    "agent_coder_enabled": False,
    "agent_debugger_enabled": False,
    "memory_system_enabled": False,
    "multi_agent_enabled": False,
    "autonomous_ui_enabled": False,
    "webhook_receiver_enabled": False,
    "compression_pipeline_enabled": True,     # on by default, no functional downside
}

# Environment variable prefix for global overrides
ENV_PREFIX = "AEP_FLAG_"


class FeatureFlagService:
    """Runtime feature flag evaluation with per-tenant overrides.

    Evaluation order (first match wins):
    1. Per-tenant DB override
    2. Environment variable override (AEP_FLAG_<NAME>=true/false)
    3. DEFAULT_FLAGS
    """

    def __init__(self) -> None:
        self._tenant_overrides: dict[str, dict[str, bool]] = {}
        self._env_cache: dict[str, bool] = self._load_env_flags()

    def _load_env_flags(self) -> dict[str, bool]:
        """Load global flag overrides from environment variables."""
        env_flags: dict[str, bool] = {}
        for flag_name in DEFAULT_FLAGS:
            env_key = f"{ENV_PREFIX}{flag_name.upper()}"
            env_val = os.environ.get(env_key)
            if env_val is not None:
                env_flags[flag_name] = env_val.lower() in ("true", "1", "yes")
                log.info("feature_flag.env_override", flag=flag_name, value=env_flags[flag_name])
        return env_flags

    def is_enabled(self, flag: str, tenant_id: Optional[str] = None) -> bool:
        """Check if a feature flag is enabled.

        Args:
            flag: The flag name (e.g. 'llm_gateway_enabled')
            tenant_id: Optional tenant ID for per-tenant override

        Returns:
            True if the flag is enabled
        """
        # 1. Per-tenant override
        if tenant_id and tenant_id in self._tenant_overrides:
            tenant_flags = self._tenant_overrides[tenant_id]
            if flag in tenant_flags:
                return tenant_flags[flag]

        # 2. Environment variable override
        if flag in self._env_cache:
            return self._env_cache[flag]

        # 3. Default
        return DEFAULT_FLAGS.get(flag, False)

    def set_tenant_override(self, tenant_id: str, flag: str, enabled: bool) -> None:
        """Set a per-tenant flag override (in-memory; persisted by caller)."""
        if tenant_id not in self._tenant_overrides:
            self._tenant_overrides[tenant_id] = {}
        self._tenant_overrides[tenant_id][flag] = enabled
        log.info("feature_flag.tenant_override_set", tenant=tenant_id, flag=flag, enabled=enabled)

    def clear_tenant_override(self, tenant_id: str, flag: str) -> None:
        """Remove a per-tenant override, falling back to env/default."""
        if tenant_id in self._tenant_overrides:
            self._tenant_overrides[tenant_id].pop(flag, None)

    def get_all_flags(self, tenant_id: Optional[str] = None) -> dict[str, bool]:
        """Return the full flag state for a tenant (or global defaults)."""
        result = dict(DEFAULT_FLAGS)
        result.update(self._env_cache)
        if tenant_id and tenant_id in self._tenant_overrides:
            result.update(self._tenant_overrides[tenant_id])
        return result

    def require(self, flag: str, tenant_id: Optional[str] = None) -> None:
        """Raise if a flag is disabled. Use as a guard in feature-gated code paths."""
        if not self.is_enabled(flag, tenant_id):
            raise FeatureDisabledError(flag)

    def refresh_env(self) -> None:
        """Reload environment variable overrides (call after env change)."""
        self._env_cache = self._load_env_flags()


class FeatureDisabledError(Exception):
    """Raised when a feature is accessed but its flag is disabled."""

    def __init__(self, flag: str) -> None:
        self.flag = flag
        super().__init__(f"Feature '{flag}' is disabled")


# ─── Decorator for Feature-Gated Endpoints ───────────────────────────────────

def feature_required(flag: str):
    """Decorator that gates a FastAPI endpoint behind a feature flag.

    Usage:
        @router.post("/LLM/chat")
        @feature_required("llm_gateway_enabled")
        async def llm_chat(...): ...
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            feature_flags.require(flag)
            return await func(*args, **kwargs)
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper
    return decorator


# Singleton
feature_flags = FeatureFlagService()
