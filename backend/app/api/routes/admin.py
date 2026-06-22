"""Admin endpoints — gated by aep:admin RBAC.

Priority 5: Quota Dashboard
  GET /admin/quota returns a snapshot of per-provider, per-model quota usage
  and circuit-breaker status.
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.core.config import settings
from app.core.rbac import Role, Permission, rbac
from app.core.security import get_current_user
from app.llm.gateway import llm_gateway
from app.models.user import User

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/quota")
async def get_quota_snapshot(user: User = Depends(get_current_user)) -> list[dict[str, Any]]:
    """Return per-provider, per-model quota usage and circuit-breaker status.

    Requires the `aep:admin` role.
    """
    rbac.initialize_from_auth(str(user.id), is_admin_email=user.email.lower() in settings.allowed_emails_set)
    if Role.ADMIN not in rbac.get_user_roles(str(user.id)):
        raise HTTPException(status_code=403, detail="Requires aep:admin role")

    # Ensure the singleton gateway is initialized
    if not llm_gateway._initialized:
        llm_gateway.initialize()

    snapshot: list[dict[str, Any]] = []
    for provider_name, provider in llm_gateway.providers.items():
        if not provider.is_configured():
            continue
        for model in provider.config.models:
            usage = llm_gateway.quota.get_usage(provider_name, model)
            breaker = llm_gateway.breaker.get_state(provider_name, model)
            snapshot.append({
                "provider": provider_name,
                "model": model,
                "rpm": {
                    "used": usage.get("rpm", 0),
                    "limit": provider.config.limits.get("rpm", 0),
                },
                "rpd": {
                    "used": usage.get("rpd", 0),
                    "limit": provider.config.limits.get("rpd", 0),
                },
                "tpm": {
                    "used": usage.get("tpm", 0),
                    "limit": provider.config.limits.get("tpm", 0),
                },
                "breakerStatus": "cooling_down" if breaker.get("cooling_down") else "healthy",
                "cooldownExpiresAt": _cooldown_expires_at(breaker.get("cooldown_remaining", 0)),
            })
    return snapshot


def _cooldown_expires_at(remaining_seconds: float) -> str | None:
    if remaining_seconds <= 0:
        return None
    return str(int(time.time() + remaining_seconds))
