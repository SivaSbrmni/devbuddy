"""
LLM configuration API.

GET  /api/v1/llm/config   — return current provider/model (no key exposed)
PUT  /api/v1/llm/config   — persist provider/model/key to .env file, reload settings
GET  /api/v1/llm/models   — list available models from the configured provider
"""
import os
import re
import httpx
import asyncio
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.core.security import get_current_user
from app.core.config import settings
from app.core.logger import get_logger

router = APIRouter(prefix="/llm", tags=["llm"])
logger = get_logger("llm_config")

ENV_FILE = Path(__file__).parent.parent.parent / ".env"

# ── Known Llama/meta models per provider ─────────────────────────────────────
KNOWN_MODELS: dict[str, list[str]] = {
    "groq": [
        "llama3-8b-8192",
        "llama3-70b-8192",
        "llama-3.1-8b-instant",
        "llama-3.1-70b-versatile",
        "llama-3.3-70b-versatile",
        "llama-3.3-70b-specdec",
        "meta-llama/llama-4-scout-17b-16e-instruct",
        "meta-llama/llama-4-maverick-17b-128e-instruct",
        "mixtral-8x7b-32768",
        "gemma2-9b-it",
    ],
    "together": [
        "meta-llama/Llama-3-8b-chat-hf",
        "meta-llama/Llama-3-70b-chat-hf",
        "meta-llama/Llama-3.1-8B-Instruct-Turbo",
        "meta-llama/Llama-3.1-70B-Instruct-Turbo",
        "meta-llama/Llama-3.2-3B-Instruct-Turbo",
        "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        "mistralai/Mixtral-8x7B-Instruct-v0.1",
    ],
    "openai": [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4-turbo",
        "gpt-3.5-turbo",
    ],
    "ollama": [],   # fetched live
    "custom": [],   # fetched live or empty
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _set_env_key(key: str, value: str):
    """Write/overwrite a single key=value line in .env."""
    if not ENV_FILE.exists():
        ENV_FILE.write_text(f"{key}={value}\n")
        return
    text = ENV_FILE.read_text()
    pattern = re.compile(rf"^{re.escape(key)}\s*=.*$", re.MULTILINE)
    if pattern.search(text):
        text = pattern.sub(f"{key}={value}", text)
    else:
        text = text.rstrip("\n") + f"\n{key}={value}\n"
    ENV_FILE.write_text(text)


async def _fetch_ollama_models() -> list[str]:
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(f"{settings.OLLAMA_URL}/api/tags")
            if r.status_code == 200:
                return [m["name"] for m in r.json().get("models", [])]
    except Exception as e:
        logger.warning("ollama_models_fetch_failed", error=str(e))
    return []


async def _fetch_openai_compat_models(base: str, api_key: str) -> list[str]:
    try:
        async with httpx.AsyncClient(timeout=8) as c:
            r = await c.get(
                f"{base}/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            if r.status_code == 200:
                data = r.json().get("data", [])
                return sorted([m["id"] for m in data])
    except Exception as e:
        logger.warning("openai_compat_models_fetch_failed", error=str(e))
    return []


# ── Schemas ───────────────────────────────────────────────────────────────────

class LlmConfigIn(BaseModel):
    provider: str
    model: str
    api_key: Optional[str] = None
    api_base: Optional[str] = None


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/config")
async def get_llm_config(user: dict = Depends(get_current_user)):
    return {
        "provider":   settings.LLM_PROVIDER,
        "model":      settings.LLM_MODEL,
        "api_base":   settings.LLM_API_BASE,
        "has_api_key": bool(settings.LLM_API_KEY),
        "ollama_url": settings.OLLAMA_URL,
    }


@router.put("/config")
async def update_llm_config(body: LlmConfigIn, user: dict = Depends(get_current_user)):
    valid_providers = {"ollama", "openai", "groq", "together", "custom"}
    if body.provider not in valid_providers:
        raise HTTPException(400, f"provider must be one of {valid_providers}")

    _set_env_key("LLM_PROVIDER", body.provider)
    _set_env_key("LLM_MODEL", body.model)
    if body.api_key:
        _set_env_key("LLM_API_KEY", body.api_key)
    if body.api_base:
        _set_env_key("LLM_API_BASE", body.api_base)

    # Patch settings in-memory so current process picks it up immediately
    # (uvicorn --reload will also restart on .env change)
    settings.LLM_PROVIDER = body.provider   # type: ignore[assignment]
    settings.LLM_MODEL    = body.model       # type: ignore[assignment]
    if body.api_key:
        settings.LLM_API_KEY = body.api_key  # type: ignore[assignment]
    if body.api_base:
        settings.LLM_API_BASE = body.api_base  # type: ignore[assignment]

    logger.info("llm_config_updated", provider=body.provider, model=body.model)
    return {"ok": True, "provider": body.provider, "model": body.model}


@router.get("/models")
async def list_llm_models(
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    prov = provider or settings.LLM_PROVIDER
    key  = api_key  or settings.LLM_API_KEY or ""

    if prov == "ollama":
        models = await _fetch_ollama_models()
        if not models:
            models = [settings.LLM_MODEL]
    elif prov in ("groq", "together", "openai"):
        # Try live fetch first, fall back to known static list
        base = {
            "groq":     "https://api.groq.com/openai/v1",
            "together": "https://api.together.xyz/v1",
            "openai":   "https://api.openai.com/v1",
        }[prov]
        if key:
            models = await _fetch_openai_compat_models(base, key)
        else:
            models = []
        if not models:
            models = KNOWN_MODELS.get(prov, [])
    elif prov == "custom":
        base = settings.LLM_API_BASE or ""
        if base and key:
            models = await _fetch_openai_compat_models(base, key)
        else:
            models = []
    else:
        models = []

    return {"provider": prov, "models": models, "count": len(models)}
