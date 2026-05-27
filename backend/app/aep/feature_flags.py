"""
Feature flag service for the AEP layer.

Every component of the autonomous engineering platform is individually
toggleable through this service. Flags are resolved with the following
precedence (first match wins):

    1. Per-tenant DB row in ``aep_feature_flags`` (``tenant_id`` set,
       matching the requesting tenant)
    2. Global DB row in ``aep_feature_flags`` (``tenant_id IS NULL``)
    3. Environment variable ``AEP_FLAG_<UPPER_FLAG_NAME>`` (truthy =
       enabled). Useful for one-off toggling in CI / local dev without
       touching the database.
    4. The flag's :class:`FlagSpec` ``default`` (always ``False`` for
       AEP capability flags; ``True`` only for the
       ``human_approval_required`` safety flag).

Lookups are async, DB-backed, and cached in-process with a short TTL
so hot paths (e.g. middleware) do not hammer Postgres. Cache
invalidation is event-driven: writes via :meth:`set` flush the cache.

The service is intentionally read-mostly and tolerant of DB outages —
if the lookup fails it falls back to env vars / defaults rather than
raising. The autonomous layer must NEVER break the host application
because the flag table is unreachable.
"""
from __future__ import annotations

import asyncio
import os
import time
import uuid
from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import get_logger
from app.aep.models import AepFeatureFlag

logger = get_logger("aep.feature_flags")

_TRUTHY = {"1", "true", "yes", "on", "enabled"}
_FALSY = {"0", "false", "no", "off", "disabled", ""}


# ─────────────────────────────────────────────────────────────────────────────
# Flag registry
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class FlagSpec:
    """Declarative metadata for a feature flag."""

    name: str
    default: bool
    description: str
    phase: int

    @property
    def env_var(self) -> str:
        return f"AEP_FLAG_{self.name.upper()}"


#: Canonical registry of every AEP feature flag. New flags MUST be
#: added here so the admin UI / list endpoint can discover them.
FLAGS: dict[str, FlagSpec] = {
    spec.name: spec
    for spec in (
        FlagSpec(
            name="autonomous_engine_enabled",
            default=False,
            description="Master switch for the entire AEP layer. When false, every other AEP flag is forced false regardless of its own value.",
            phase=6,
        ),
        FlagSpec(
            name="llm_gateway_enabled",
            default=False,
            description="Enables the /LLM/* gateway routes. When false they return 503.",
            phase=1,
        ),
        FlagSpec(
            name="webhook_receiver_enabled",
            default=False,
            description="Accepts GitHub webhooks at /api/v1/aep/webhooks/github.",
            phase=2,
        ),
        FlagSpec(
            name="github_actions_runtime_enabled",
            default=False,
            description="Allows the GHA Runtime Manager to generate workflow YAML and trigger workflow runs.",
            phase=3,
        ),
        FlagSpec(
            name="agent_planner_enabled",
            default=False,
            description="Loads the Planner agent into the plugin registry.",
            phase=3,
        ),
        FlagSpec(
            name="agent_coder_enabled",
            default=False,
            description="Loads the Coding agent into the plugin registry.",
            phase=3,
        ),
        FlagSpec(
            name="agent_debugger_enabled",
            default=False,
            description="Loads the Debugging agent into the plugin registry.",
            phase=5,
        ),
        FlagSpec(
            name="agent_tester_enabled",
            default=False,
            description="Loads the Test agent into the plugin registry.",
            phase=5,
        ),
        FlagSpec(
            name="agent_reviewer_enabled",
            default=False,
            description="Loads the Review agent into the plugin registry.",
            phase=5,
        ),
        FlagSpec(
            name="agent_security_audit_enabled",
            default=False,
            description="Loads the Security Audit agent into the plugin registry.",
            phase=5,
        ),
        FlagSpec(
            name="agent_documentation_enabled",
            default=False,
            description="Loads the Documentation agent into the plugin registry.",
            phase=5,
        ),
        FlagSpec(
            name="agent_devops_enabled",
            default=False,
            description="Loads the DevOps agent into the plugin registry.",
            phase=5,
        ),
        FlagSpec(
            name="memory_system_enabled",
            default=False,
            description="Enables the long-term memory store (aep_memory_entries) and the Context Engine.",
            phase=4,
        ),
        FlagSpec(
            name="multi_agent_enabled",
            default=False,
            description="Enables the Coordinator agent and multi-agent orchestration.",
            phase=5,
        ),
        FlagSpec(
            name="autonomous_ui_enabled",
            default=False,
            description="Exposes the AEP frontend module routes.",
            phase=5,
        ),
        FlagSpec(
            name="human_approval_required",
            default=True,  # safety default
            description="When true, executions pause at AWAITING_APPROVAL before any destructive operation. Defaults TRUE for safety.",
            phase=0,
        ),
    )
}

# Flags that, when ``autonomous_engine_enabled`` is false, should still
# be allowed to evaluate independently. Currently only the master flag
# itself and the safety default. Every other flag is forced false when
# the master is off.
_MASTER_FLAG = "autonomous_engine_enabled"
_INDEPENDENT_FLAGS = frozenset({_MASTER_FLAG, "human_approval_required"})


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _parse_env_bool(raw: Optional[str]) -> Optional[bool]:
    """Parse an env var value into a tri-state bool (``None`` = unset)."""
    if raw is None:
        return None
    s = raw.strip().lower()
    if s in _TRUTHY:
        return True
    if s in _FALSY:
        return False
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Service
# ─────────────────────────────────────────────────────────────────────────────


class FeatureFlagService:
    """Resolves feature flag values with per-tenant overrides.

    Instances are cheap to create but the cache is per-instance, so a
    single application-wide instance should be used. The recommended
    pattern is to obtain it via :func:`get_feature_flag_service`.
    """

    CACHE_TTL_SECONDS = 5.0

    def __init__(self) -> None:
        # cache: (tenant_id_str_or_global, name) -> (value, expires_at)
        self._cache: dict[tuple[str, str], tuple[bool, float]] = {}
        self._lock = asyncio.Lock()

    # ── Public API ──────────────────────────────────────────────────────

    def spec(self, name: str) -> Optional[FlagSpec]:
        """Return the :class:`FlagSpec` for ``name`` or ``None`` if unknown."""
        return FLAGS.get(name)

    def list_specs(self) -> list[FlagSpec]:
        """Return every registered :class:`FlagSpec`, sorted by name."""
        return sorted(FLAGS.values(), key=lambda s: s.name)

    async def is_enabled(
        self,
        name: str,
        *,
        tenant_id: Optional[uuid.UUID] = None,
        db: Optional[AsyncSession] = None,
    ) -> bool:
        """Resolve the effective value of a flag for an optional tenant.

        Unknown flag names always evaluate to ``False`` and emit a
        warning log line — this keeps mis-typed checks from accidentally
        activating capabilities.
        """
        spec = FLAGS.get(name)
        if spec is None:
            logger.warning("unknown_feature_flag", name=name)
            return False

        # If the master switch is off, every capability flag is forced
        # off. The master flag itself and ``human_approval_required``
        # bypass this gate so they can be evaluated independently.
        if name not in _INDEPENDENT_FLAGS:
            master = await self._resolve(_MASTER_FLAG, tenant_id, db)
            if master is False:
                return False

        return await self._resolve(name, tenant_id, db)

    async def set(
        self,
        name: str,
        enabled: bool,
        *,
        tenant_id: Optional[uuid.UUID] = None,
        db: AsyncSession,
    ) -> AepFeatureFlag:
        """Persist a flag value. ``tenant_id=None`` writes the global default."""
        spec = FLAGS.get(name)
        if spec is None:
            raise ValueError(f"unknown feature flag: {name!r}")

        existing = await self._fetch_row(name, tenant_id, db)
        if existing is None:
            row = AepFeatureFlag(
                tenant_id=tenant_id,
                name=name,
                enabled=enabled,
                description=spec.description,
            )
            db.add(row)
        else:
            existing.enabled = enabled
            row = existing

        await db.flush()
        self._invalidate(name, tenant_id)
        logger.info(
            "feature_flag_set",
            name=name,
            tenant_id=str(tenant_id) if tenant_id else None,
            enabled=enabled,
        )
        return row

    async def list_resolved(
        self,
        *,
        tenant_id: Optional[uuid.UUID] = None,
        db: Optional[AsyncSession] = None,
    ) -> list[dict[str, Any]]:
        """List every flag together with its resolved value for a tenant."""
        out: list[dict[str, Any]] = []
        for spec in self.list_specs():
            value = await self.is_enabled(spec.name, tenant_id=tenant_id, db=db)
            out.append(
                {
                    "name": spec.name,
                    "enabled": value,
                    "default": spec.default,
                    "description": spec.description,
                    "phase": spec.phase,
                }
            )
        return out

    def invalidate_cache(self) -> None:
        """Drop every cached value. Useful for tests / manual flushes."""
        self._cache.clear()

    # ── Internals ───────────────────────────────────────────────────────

    async def _resolve(
        self,
        name: str,
        tenant_id: Optional[uuid.UUID],
        db: Optional[AsyncSession],
    ) -> bool:
        cached = self._read_cache(name, tenant_id)
        if cached is not None:
            return cached

        spec = FLAGS[name]
        value = spec.default

        # 1. DB lookup (per-tenant then global)
        if db is not None:
            try:
                row = await self._fetch_row(name, tenant_id, db)
                if row is None and tenant_id is not None:
                    row = await self._fetch_row(name, None, db)
                if row is not None:
                    value = bool(row.enabled)
                    self._write_cache(name, tenant_id, value)
                    return value
            except Exception as exc:  # noqa: BLE001
                # Tolerate DB outages — fall through to env/default.
                logger.warning(
                    "feature_flag_db_lookup_failed",
                    name=name,
                    error=str(exc),
                )

        # 2. Env var fallback
        env_value = _parse_env_bool(os.environ.get(spec.env_var))
        if env_value is not None:
            value = env_value

        self._write_cache(name, tenant_id, value)
        return value

    async def _fetch_row(
        self,
        name: str,
        tenant_id: Optional[uuid.UUID],
        db: AsyncSession,
    ) -> Optional[AepFeatureFlag]:
        stmt = select(AepFeatureFlag).where(AepFeatureFlag.name == name)
        if tenant_id is None:
            stmt = stmt.where(AepFeatureFlag.tenant_id.is_(None))
        else:
            stmt = stmt.where(AepFeatureFlag.tenant_id == tenant_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    # ── Cache primitives ───────────────────────────────────────────────

    def _cache_key(self, name: str, tenant_id: Optional[uuid.UUID]) -> tuple[str, str]:
        return (str(tenant_id) if tenant_id else "__global__", name)

    def _read_cache(
        self, name: str, tenant_id: Optional[uuid.UUID]
    ) -> Optional[bool]:
        entry = self._cache.get(self._cache_key(name, tenant_id))
        if entry is None:
            return None
        value, expires_at = entry
        if expires_at < time.monotonic():
            self._cache.pop(self._cache_key(name, tenant_id), None)
            return None
        return value

    def _write_cache(
        self, name: str, tenant_id: Optional[uuid.UUID], value: bool
    ) -> None:
        self._cache[self._cache_key(name, tenant_id)] = (
            value,
            time.monotonic() + self.CACHE_TTL_SECONDS,
        )

    def _invalidate(self, name: str, tenant_id: Optional[uuid.UUID]) -> None:
        self._cache.pop(self._cache_key(name, tenant_id), None)
        # Also drop the global-cache entry — a per-tenant write does not
        # logically invalidate the global value, but a global write
        # invalidates every tenant entry.
        if tenant_id is None:
            self._cache = {k: v for k, v in self._cache.items() if k[1] != name}


# ─────────────────────────────────────────────────────────────────────────────
# Singleton accessor
# ─────────────────────────────────────────────────────────────────────────────

_service: Optional[FeatureFlagService] = None


def get_feature_flag_service() -> FeatureFlagService:
    """Return the application-wide :class:`FeatureFlagService` instance."""
    global _service
    if _service is None:
        _service = FeatureFlagService()
    return _service


def reset_feature_flag_service() -> None:
    """Reset the singleton. Test-only helper."""
    global _service
    _service = None


__all__ = [
    "FlagSpec",
    "FLAGS",
    "FeatureFlagService",
    "get_feature_flag_service",
    "reset_feature_flag_service",
]
