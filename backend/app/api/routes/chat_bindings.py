"""Chat platform bindings API — Priority 1.

Authenticated users can generate a one-time link code to bind their Telegram
chat. The chat bot consumes the code via /webhooks/telegram.
"""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.feature_flags import feature_flags
from app.core.security import get_current_user
from app.models.aep import AepChatBinding
from app.models.user import User

router = APIRouter(prefix="/chat-bindings", tags=["chat-bindings"])


@router.post("/telegram/link-code")
async def create_telegram_link_code(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Generate a one-time link code for Telegram binding."""
    if not feature_flags.is_enabled("telegram_bot_enabled"):
        raise HTTPException(status_code=503, detail="Telegram bot is not enabled")

    link_code = secrets.token_urlsafe(16)
    binding = AepChatBinding(
        tenant_id=str(user.org_id),
        user_id=str(user.id),
        platform="telegram",
        platform_chat_id="pending",
        link_code=link_code,
        status="pending",
    )
    db.add(binding)
    await db.flush()
    return {"link_code": link_code, "platform": "telegram", "expires_in_seconds": 600}


@router.get("/telegram/status")
async def get_telegram_binding_status(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Return whether the user has an active Telegram binding."""
    from sqlalchemy import select

    stmt = select(AepChatBinding).where(
        AepChatBinding.user_id == str(user.id),
        AepChatBinding.platform == "telegram",
        AepChatBinding.status == "active",
    )
    result = await db.execute(stmt)
    binding = result.scalar_one_or_none()
    return {"active": binding is not None, "platform_chat_id": binding.platform_chat_id if binding else None}
