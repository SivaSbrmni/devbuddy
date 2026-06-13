"""Secrets management API — Phase 6.

CRUD for encrypted secrets. Never returns plaintext values in
list/get responses — only metadata.

Spec reference: AGENTS.md Phase 6 — SecretManager, spec §10.1.
"""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.aep.observability import aep_logger
from app.aep.security.secrets import SecretManagerError, get_secret_manager
from app.core.database import get_db
from app.core.security import get_current_user

router = APIRouter(prefix="/aep/secrets", tags=["aep-secrets"])
_logger = aep_logger("aep.api.secrets")


class SecretCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    value: str = Field(..., min_length=1)
    secret_type: str = Field(default="generic", max_length=50)


class SecretOut(BaseModel):
    id: str
    name: str
    secret_type: str
    created_at: str | None
    updated_at: str | None
    rotated_at: str | None


class SecretListOut(BaseModel):
    secrets: list[SecretOut]
    count: int


def _tenant_id(user: dict[str, Any]) -> uuid.UUID:
    payload = user.get("payload") or {}
    tid = payload.get("tenant_id") or payload.get("sub")
    return uuid.UUID(str(tid))


@router.post("", response_model=SecretOut, status_code=status.HTTP_201_CREATED)
async def store_secret(
    body: SecretCreate,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SecretOut:
    """Store an encrypted secret."""
    sm = get_secret_manager()
    try:
        result = await sm.store_secret(
            tenant_id=_tenant_id(user),
            name=body.name,
            value=body.value,
            secret_type=body.secret_type,
            db=db,
        )
    except SecretManagerError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return SecretOut(
        id=result["id"],
        name=result["name"],
        secret_type=body.secret_type,
        created_at=None,
        updated_at=None,
        rotated_at=None,
    )


@router.get("", response_model=SecretListOut)
async def list_secrets(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SecretListOut:
    """List secret metadata (never plaintext values)."""
    sm = get_secret_manager()
    secrets = await sm.list_secrets(tenant_id=_tenant_id(user), db=db)
    return SecretListOut(
        secrets=[SecretOut(**s) for s in secrets],
        count=len(secrets),
    )


@router.delete("/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_secret(
    name: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a secret."""
    sm = get_secret_manager()
    deleted = await sm.delete_secret(
        tenant_id=_tenant_id(user),
        name=name,
        db=db,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Secret '{name}' not found")
