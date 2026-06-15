"""Models endpoint — fetches live models using per-user API keys."""

from __future__ import annotations

import asyncio
from typing import Any, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from jose import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.crypto import crypto
from app.core.deps import get_db
from app.models.user_settings import UserSettings

router = APIRouter(prefix="/models", tags=["models"])

# Static known models per provider
_KNOWN_MODELS = {
    "anthropic": [
        {"id": "claude-sonnet-4-20250514", "label": "Claude Sonnet 4", "provider": "anthropic", "family": "anthropic"},
    ],
    "llama": [
        {"id": "llama-4-scout-17b-16e-instruct", "label": "Llama 4 Scout", "provider": "llama", "family": "llama"},
    ],
}

# Cache for Ollama models (60s TTL)
_ollama_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}
_CACHE_TTL = 60.0


def _get_email_from_token(token: str | None) -> str | None:
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        return payload.get("email")
    except Exception:
        return None


async def _fetch_ollama_models(base_url: str, api_key: str) -> list[dict[str, Any]]:
    """Fetch models from Ollama /api/tags."""
    try:
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        async with httpx.AsyncClient(
            base_url=base_url or settings.OLLAMA_API_BASE,
            headers=headers,
            timeout=30.0,
        ) as client:
            resp = await client.get("/api/tags")
            resp.raise_for_status()
            data = resp.json()

            models = []
            for m in data.get("models", []):
                name = m.get("name", "")
                label = name
                family = "ollama"
                if ":" in name:
                    base_name = name.split(":")[0]
                    label = base_name.replace("-", " ").title()
                models.append({
                    "id": name,
                    "label": label,
                    "provider": "ollama",
                    "family": family,
                })
            return models
    except Exception as e:
        print(f"Failed to fetch Ollama models: {e}")
        return []


@router.get("")
async def list_models(
    token: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """List available models using the user's configured API keys."""
    email = _get_email_from_token(token)
    models: list[dict[str, Any]] = []

    user_keys: dict[str, Any] = {}
    if email:
        result = await db.execute(select(UserSettings).where(UserSettings.email == email))
        row = result.scalar_one_or_none()
        if row:
            user_keys = crypto.decrypt_dict(row.api_keys)

    # Anthropic
    anthropic_cfg = user_keys.get("anthropic") or {}
    if anthropic_cfg.get("key") or settings.ANTHROPIC_API_KEY:
        models.extend(_KNOWN_MODELS.get("anthropic", []))

    # Llama
    llama_cfg = user_keys.get("llama") or {}
    if llama_cfg.get("key") or settings.LLAMA_API_KEY:
        models.extend(_KNOWN_MODELS.get("llama", []))

    # Ollama — fetch live list
    ollama_cfg = user_keys.get("ollama") or {}
    ollama_key = ollama_cfg.get("key") or settings.OLLAMA_API_KEY
    ollama_base = ollama_cfg.get("base_url") or settings.OLLAMA_API_BASE
    if ollama_key:
        cache_key = f"{ollama_base}:{ollama_key[:4]}"
        now = asyncio.get_event_loop().time()
        cached = _ollama_cache.get(cache_key)
        if cached and now - cached[0] < _CACHE_TTL:
            models.extend(cached[1])
        else:
            ollama_models = await _fetch_ollama_models(ollama_base, ollama_key)
            _ollama_cache[cache_key] = (now, ollama_models)
            models.extend(ollama_models)

    # Deduplicate
    seen = set()
    deduped = []
    for m in models:
        key = m["id"]
        if key not in seen:
            seen.add(key)
            deduped.append(m)

    return deduped
