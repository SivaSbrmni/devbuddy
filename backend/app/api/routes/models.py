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
    "ollama": [
        {"id": "qwen3-coder:480b", "label": "Qwen 3 Coder", "provider": "ollama", "family": "ollama"},
        {"id": "llama3.3:latest", "label": "Llama 3.3", "provider": "ollama", "family": "ollama"},
        {"id": "deepseek-coder:latest", "label": "DeepSeek Coder", "provider": "ollama", "family": "ollama"},
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
    """Fetch models from Ollama /api/tags. Fast timeout for non-blocking fallback."""
    try:
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        async with httpx.AsyncClient(
            base_url=base_url or settings.OLLAMA_API_BASE,
            headers=headers,
            timeout=2.0,  # Fast timeout - don't block if Ollama not running
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
        # Silently fail - Ollama not running is expected in many deployments
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

    # Ollama — try live fetch first from user's config or default localhost
    ollama_cfg = user_keys.get("ollama") or {}
    ollama_key = ollama_cfg.get("key") or settings.OLLAMA_API_KEY
    ollama_base = ollama_cfg.get("base_url") or settings.OLLAMA_API_BASE
    
    # Always try to fetch live Ollama models (fast timeout, non-blocking)
    cache_key = f"{ollama_base}:{ollama_key[:4] if ollama_key else 'nokey'}"
    now = asyncio.get_event_loop().time()
    cached = _ollama_cache.get(cache_key)
    
    if cached and now - cached[0] < _CACHE_TTL:
        models.extend(cached[1])
    else:
        ollama_models = await _fetch_ollama_models(ollama_base, ollama_key)
        if ollama_models:
            _ollama_cache[cache_key] = (now, ollama_models)
            models.extend(ollama_models)
        else:
            # Fallback to known static models if Ollama is not running
            models.extend(_KNOWN_MODELS.get("ollama", []))

    # Deduplicate
    seen = set()
    deduped = []
    for m in models:
        key = m["id"]
        if key not in seen:
            seen.add(key)
            deduped.append(m)

    return deduped
