"""
AEP administrative API — Phase 0.

Routes mounted at ``/api/v1/aep`` for operating the autonomous
engineering layer:

    GET    /api/v1/aep/flags                    — list every flag + current value
    PUT    /api/v1/aep/flags/{name}             — set a flag (global or per-tenant)
    GET    /api/v1/aep/plugins                  — diagnostics for the plugin registry
    GET    /api/v1/aep/status                   — high-level health of the AEP layer

The routes themselves are always reachable, but every write is
authenticated through the existing Supabase JWT scheme. They do NOT
require ``autonomous_engine_enabled`` to be on — the master switch
controls *capabilities*, not *administration*.

RBAC is wired through the Compatibility Adapter in later phases. In
Phase 0 any authenticated user can read; writes are restricted to the
``aep:admin`` JWT role claim if present, falling back to allowing any
authenticated user (so the platform owner can bootstrap the system).
"""
from __future__ import annotations

import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.logger import get_logger
from app.core.security import get_current_user
from app.aep.feature_flags import FLAGS, get_feature_flag_service
from app.aep.plugins import get_plugin_registry

router = APIRouter(prefix="/aep", tags=["aep-admin"])
logger = get_logger("aep.api.admin")


# ─────────────────────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────────────────────


class FlagOut(BaseModel):
    name: str
    enabled: bool
    default: bool
    description: str
    phase: int


class FlagUpdate(BaseModel):
    enabled: bool
    tenant_id: Optional[uuid.UUID] = Field(
        default=None,
        description="When omitted, the flag is set globally (tenant_id IS NULL).",
    )


class FlagListOut(BaseModel):
    flags: list[FlagOut]
    master_flag: str = "autonomous_engine_enabled"


class PluginInfoOut(BaseModel):
    name: str
    plugin_class: str
    feature_flag: str
    model: str
    fallback_model: Optional[str] = None
    active: bool
    description: str


class AepStatusOut(BaseModel):
    phase: int = 0
    master_enabled: bool
    flags_total: int
    flags_enabled: int
    plugins_registered: int
    plugins_active: int


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _has_admin_role(user: dict[str, Any]) -> bool:
    """Return True if the JWT carries an explicit aep:admin role.

    The existing Supabase JWT payload exposes the user's role under
    ``role`` (string) or ``roles`` (list). When neither claim is
    present we fall back to allowing the request — Phase 6 will
    tighten this once the host RBAC system is integrated.
    """
    payload = user.get("payload") or {}
    role = payload.get("role")
    roles = payload.get("roles") or []
    if isinstance(role, str) and role == "aep:admin":
        return True
    if isinstance(roles, list) and "aep:admin" in roles:
        return True
    # No explicit role claim → bootstrap mode: allow.
    return role is None and not roles


# ─────────────────────────────────────────────────────────────────────────────
# Routes — feature flags
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/flags", response_model=FlagListOut)
async def list_flags(
    tenant_id: Optional[uuid.UUID] = None,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FlagListOut:
    """Return every registered AEP flag with its resolved value."""
    ff = get_feature_flag_service()
    resolved = await ff.list_resolved(tenant_id=tenant_id, db=db)
    return FlagListOut(flags=[FlagOut(**item) for item in resolved])


@router.put("/flags/{name}", response_model=FlagOut)
async def update_flag(
    name: str,
    body: FlagUpdate,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FlagOut:
    """Set a flag value globally or for a single tenant."""
    if name not in FLAGS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"unknown feature flag: {name!r}",
        )
    if not _has_admin_role(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="aep:admin role required",
        )

    ff = get_feature_flag_service()
    await ff.set(name, body.enabled, tenant_id=body.tenant_id, db=db)
    # Re-resolve to capture master-flag override semantics.
    enabled = await ff.is_enabled(name, tenant_id=body.tenant_id, db=db)
    spec = FLAGS[name]
    return FlagOut(
        name=spec.name,
        enabled=enabled,
        default=spec.default,
        description=spec.description,
        phase=spec.phase,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Routes — plugin registry diagnostics
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/plugins", response_model=list[PluginInfoOut])
async def list_plugins(user: dict = Depends(get_current_user)) -> list[PluginInfoOut]:
    """Return diagnostic info about every registered plugin."""
    registry = get_plugin_registry()
    raw = registry.info()
    return [
        PluginInfoOut(
            name=item["name"],
            plugin_class=item["class"],
            feature_flag=item["feature_flag"],
            model=item["model"],
            fallback_model=item.get("fallback_model"),
            active=bool(item["active"]),
            description=item.get("description") or "",
        )
        for item in raw
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Routes — AEP status summary
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/status", response_model=AepStatusOut)
async def aep_status(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AepStatusOut:
    """High-level health and adoption summary for the AEP layer."""
    ff = get_feature_flag_service()
    registry = get_plugin_registry()
    resolved = await ff.list_resolved(db=db)
    enabled_count = sum(1 for f in resolved if f["enabled"])
    master_enabled = await ff.is_enabled("autonomous_engine_enabled", db=db)
    return AepStatusOut(
        master_enabled=master_enabled,
        flags_total=len(resolved),
        flags_enabled=enabled_count,
        plugins_registered=len(registry.list_registered()),
        plugins_active=len(registry.list_active()),
    )


__all__ = ["router"]
