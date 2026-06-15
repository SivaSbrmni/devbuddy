"""User settings — API keys, model preferences."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.crypto import crypto
from app.core.deps import get_db
from app.models.user_settings import UserSettings

router = APIRouter(prefix="/settings", tags=["settings"])


class ProviderConfig(BaseModel):
    key: str = Field(default="", description="API key (will be encrypted at rest)")
    base_url: str = Field(default="", description="Optional override for API base URL")


class UserSettingsUpdate(BaseModel):
    anthropic: ProviderConfig | None = None
    ollama: ProviderConfig | None = None
    llama: ProviderConfig | None = None


def _get_user_email(token: str) -> str:
    from jose import jwt
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        return payload["email"]
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


@router.get("")
async def get_settings(token: str, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Return decrypted settings for the authenticated user."""
    email = _get_user_email(token)
    result = await db.execute(select(UserSettings).where(UserSettings.email == email))
    row = result.scalar_one_or_none()

    if not row:
        return {"providers": {}}

    decrypted = crypto.decrypt_dict(row.api_keys)
    # Strip actual keys from response, only show presence + base_url
    providers: dict[str, Any] = {}
    for name, cfg in decrypted.items():
        providers[name] = {
            "configured": bool(cfg.get("key")),
            "base_url": cfg.get("base_url", ""),
        }
    return {"providers": providers}


@router.post("")
async def update_settings(
    token: str,
    body: UserSettingsUpdate,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Save API keys (encrypts at rest)."""
    email = _get_user_email(token)

    # Build flat dict
    api_keys: dict[str, Any] = {}
    if body.anthropic:
        api_keys["anthropic"] = body.anthropic.model_dump()
    if body.ollama:
        api_keys["ollama"] = body.ollama.model_dump()
    if body.llama:
        api_keys["llama"] = body.llama.model_dump()

    encrypted = crypto.encrypt_dict(api_keys)

    result = await db.execute(select(UserSettings).where(UserSettings.email == email))
    row = result.scalar_one_or_none()

    if row:
        row.api_keys = encrypted
    else:
        row = UserSettings(email=email, api_keys=encrypted)
        db.add(row)

    await db.commit()
    return {"status": "saved"}


@router.delete("")
async def delete_settings(token: str, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Remove all stored API keys."""
    email = _get_user_email(token)
    result = await db.execute(select(UserSettings).where(UserSettings.email == email))
    row = result.scalar_one_or_none()
    if row:
        await db.delete(row)
        await db.commit()
    return {"status": "deleted"}
