"""Models endpoint — fetches live Ollama models + Claude."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException

from app.core.config import settings

router = APIRouter(prefix="/models", tags=["models"])

# Cache for Ollama models (60s TTL)
_ollama_models_cache: list[dict[str, Any]] = []
_ollama_cache_time: float = 0.0
_CACHE_TTL = 60.0


async def _fetch_ollama_models() -> list[dict[str, Any]]:
    """Fetch models from Ollama /api/tags with caching."""
    global _ollama_models_cache, _ollama_cache_time
    
    now = asyncio.get_event_loop().time()
    if now - _ollama_cache_time < _CACHE_TTL and _ollama_models_cache:
        return _ollama_models_cache
    
    if not settings.OLLAMA_API_KEY:
        return []
    
    try:
        async with httpx.AsyncClient(
            base_url=settings.OLLAMA_API_BASE,
            headers={"Authorization": f"Bearer {settings.OLLAMA_API_KEY}"},
            timeout=30.0,
        ) as client:
            resp = await client.get("/tags")
            resp.raise_for_status()
            data = resp.json()
            
            models = []
            for m in data.get("models", []):
                name = m.get("name", "")
                # Extract family/label from name if available
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
            
            _ollama_models_cache = models
            _ollama_cache_time = now
            return models
    except Exception as e:
        # Log but don't fail — return empty list
        print(f"Failed to fetch Ollama models: {e}")
        return []


@router.get("")
async def list_models() -> list[dict[str, Any]]:
    """List available models: Ollama (live) + Claude (if configured)."""
    models = []
    
    # Add Claude if API key is configured
    if settings.ANTHROPIC_API_KEY:
        models.append({
            "id": settings.ANTHROPIC_MODEL,
            "label": "Claude Sonnet 4",
            "provider": "anthropic",
            "family": "anthropic",
        })
    
    # Add Ollama models
    ollama_models = await _fetch_ollama_models()
    models.extend(ollama_models)
    
    # Fallback to static list if both are empty
    if not models:
        models = [
            {"id": "claude-sonnet-4", "label": "Claude Sonnet 4", "provider": "anthropic", "family": "anthropic"},
            {"id": "qwen3-coder:480b", "label": "Qwen3 Coder", "provider": "ollama", "family": "ollama"},
            {"id": "mistral-large-3", "label": "Mixtral 3", "provider": "ollama", "family": "ollama"},
        ]
    
    return models
