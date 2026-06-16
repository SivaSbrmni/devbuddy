"""LLM Provider API - Universal endpoint configuration.

Users can add any OpenAI-compatible endpoint without code changes.
Supports Ollama, OpenRouter, Azure, custom endpoints, etc.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.security import get_current_user
from app.core.crypto import encrypt_value, decrypt_value
from app.models.user import User

router = APIRouter(prefix="/llm-providers", tags=["llm-providers"])


# ─── Pydantic Schemas ────────────────────────────────────────────────────────

class ProviderCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    provider_type: str = Field(default="openai-compatible")
    base_url: str = Field(..., min_length=1, max_length=512)
    api_key: str = Field(default="", max_length=1000)
    headers: dict = Field(default_factory=dict)
    default_model: str = Field(..., min_length=1, max_length=100)
    available_models: List[str] = Field(default_factory=list)
    supports_streaming: bool = True
    supports_tools: bool = True
    supports_vision: bool = False
    context_size: int = Field(default=8192, ge=1024, le=200000)
    max_tokens: int = Field(default=4096, ge=1, le=32000)
    cost_per_1k_input: float = Field(default=0.0, ge=0)
    cost_per_1k_output: float = Field(default=0.0, ge=0)
    priority: int = Field(default=100, ge=1, le=1000)
    is_default: bool = False


class ProviderUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    base_url: Optional[str] = Field(None, max_length=512)
    api_key: Optional[str] = Field(None, max_length=1000)
    headers: Optional[dict] = None
    default_model: Optional[str] = Field(None, max_length=100)
    available_models: Optional[List[str]] = None
    supports_streaming: Optional[bool] = None
    supports_tools: Optional[bool] = None
    supports_vision: Optional[bool] = None
    context_size: Optional[int] = Field(None, ge=1024, le=200000)
    max_tokens: Optional[int] = Field(None, ge=1, le=32000)
    cost_per_1k_input: Optional[float] = Field(None, ge=0)
    cost_per_1k_output: Optional[float] = Field(None, ge=0)
    priority: Optional[int] = Field(None, ge=1, le=1000)
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None


class ProviderResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    provider_type: str
    base_url: str
    api_key_masked: str  # Only show last 4 chars
    headers: dict
    default_model: str
    available_models: List[str]
    supports_streaming: bool
    supports_tools: bool
    supports_vision: bool
    context_size: int
    max_tokens: int
    cost_per_1k_input: float
    cost_per_1k_output: float
    priority: int
    is_active: bool
    is_default: bool
    health_status: str
    health_message: str
    latency_ms: Optional[int]
    request_count: int
    last_used_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class TestProviderRequest(BaseModel):
    base_url: str
    api_key: str
    provider_type: str = "openai-compatible"
    model: str


class TestProviderResponse(BaseModel):
    success: bool
    latency_ms: int
    message: str
    models_available: Optional[List[str]] = None


# ─── Helper Functions ────────────────────────────────────────────────────────

def mask_api_key(key: str) -> str:
    """Show only last 4 characters of API key."""
    if not key or len(key) < 8:
        return ""
    return "••••••••" + key[-4:]


def provider_to_response(provider) -> ProviderResponse:
    """Convert DB model to API response."""
    return ProviderResponse(
        id=provider.id,
        user_id=provider.user_id,
        name=provider.name,
        provider_type=provider.provider_type,
        base_url=provider.base_url,
        api_key_masked=mask_api_key(decrypt_value(provider.api_key_encrypted)),
        headers=provider.headers,
        default_model=provider.default_model,
        available_models=provider.available_models,
        supports_streaming=provider.supports_streaming,
        supports_tools=provider.supports_tools,
        supports_vision=provider.supports_vision,
        context_size=provider.context_size,
        max_tokens=provider.max_tokens,
        cost_per_1k_input=provider.cost_per_1k_input,
        cost_per_1k_output=provider.cost_per_1k_output,
        priority=provider.priority,
        is_active=provider.is_active,
        is_default=provider.is_default,
        health_status=provider.health_status,
        health_message=provider.health_message,
        latency_ms=provider.latency_ms,
        request_count=provider.request_count,
        last_used_at=provider.last_used_at,
        created_at=provider.created_at,
        updated_at=provider.updated_at,
    )


# ─── CRUD Endpoints ───────────────────────────────────────────────────────────

@router.get("", response_model=List[ProviderResponse])
async def list_providers(
    user: User = Depends(get_current_user),
) -> List[ProviderResponse]:
    """List all LLM providers for the current user."""
    from app.db.session import async_session_factory
    from app.models.llm_provider import UserLLMProvider
    from sqlalchemy import select

    async with async_session_factory() as db:
        stmt = (
            select(UserLLMProvider)
            .where(UserLLMProvider.user_id == user.id)
            .order_by(UserLLMProvider.priority, UserLLMProvider.created_at.desc())
        )
        result = await db.execute(stmt)
        providers = result.scalars().all()
        return [provider_to_response(p) for p in providers]


@router.post("", response_model=ProviderResponse)
async def create_provider(
    req: ProviderCreate,
    user: User = Depends(get_current_user),
) -> ProviderResponse:
    """Create a new LLM provider."""
    from app.db.session import async_session_factory
    from app.models.llm_provider import UserLLMProvider

    async with async_session_factory() as db:
        # If this is set as default, unset any existing default
        if req.is_default:
            await db.execute(
                f"""
                UPDATE user_llm_providers
                SET is_default = false
                WHERE user_id = '{user.id}'
                """
            )

        provider = UserLLMProvider(
            user_id=user.id,
            name=req.name,
            provider_type=req.provider_type,
            base_url=req.base_url.rstrip("/"),
            api_key_encrypted=encrypt_value(req.api_key),
            headers=req.headers,
            default_model=req.default_model,
            available_models=req.available_models or [req.default_model],
            supports_streaming=req.supports_streaming,
            supports_tools=req.supports_tools,
            supports_vision=req.supports_vision,
            context_size=req.context_size,
            max_tokens=req.max_tokens,
            cost_per_1k_input=req.cost_per_1k_input,
            cost_per_1k_output=req.cost_per_1k_output,
            priority=req.priority,
            is_default=req.is_default,
        )

        db.add(provider)
        await db.commit()
        await db.refresh(provider)

        return provider_to_response(provider)


@router.get("/{provider_id}", response_model=ProviderResponse)
async def get_provider(
    provider_id: uuid.UUID,
    user: User = Depends(get_current_user),
) -> ProviderResponse:
    """Get a specific provider."""
    from app.db.session import async_session_factory
    from app.models.llm_provider import UserLLMProvider
    from sqlalchemy import select

    async with async_session_factory() as db:
        stmt = select(UserLLMProvider).where(
            UserLLMProvider.id == provider_id,
            UserLLMProvider.user_id == user.id,
        )
        result = await db.execute(stmt)
        provider = result.scalar_one_or_none()

        if not provider:
            raise HTTPException(status_code=404, detail="Provider not found")

        return provider_to_response(provider)


@router.patch("/{provider_id}", response_model=ProviderResponse)
async def update_provider(
    provider_id: uuid.UUID,
    req: ProviderUpdate,
    user: User = Depends(get_current_user),
) -> ProviderResponse:
    """Update a provider."""
    from app.db.session import async_session_factory
    from app.models.llm_provider import UserLLMProvider
    from sqlalchemy import select

    async with async_session_factory() as db:
        stmt = select(UserLLMProvider).where(
            UserLLMProvider.id == provider_id,
            UserLLMProvider.user_id == user.id,
        )
        result = await db.execute(stmt)
        provider = result.scalar_one_or_none()

        if not provider:
            raise HTTPException(status_code=404, detail="Provider not found")

        # If setting as default, unset others
        if req.is_default:
            await db.execute(
                f"""
                UPDATE user_llm_providers
                SET is_default = false
                WHERE user_id = '{user.id}' AND id != '{provider_id}'
                """
            )

        # Update fields
        update_data = req.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if field == "api_key" and value:
                setattr(provider, "api_key_encrypted", encrypt_value(value))
            elif field == "base_url" and value:
                setattr(provider, field, value.rstrip("/"))
            elif hasattr(provider, field):
                setattr(provider, field, value)

        await db.commit()
        await db.refresh(provider)

        return provider_to_response(provider)


@router.delete("/{provider_id}")
async def delete_provider(
    provider_id: uuid.UUID,
    user: User = Depends(get_current_user),
) -> dict:
    """Delete a provider."""
    from app.db.session import async_session_factory
    from app.models.llm_provider import UserLLMProvider
    from sqlalchemy import select

    async with async_session_factory() as db:
        stmt = select(UserLLMProvider).where(
            UserLLMProvider.id == provider_id,
            UserLLMProvider.user_id == user.id,
        )
        result = await db.execute(stmt)
        provider = result.scalar_one_or_none()

        if not provider:
            raise HTTPException(status_code=404, detail="Provider not found")

        await db.delete(provider)
        await db.commit()

        return {"deleted": True, "id": str(provider_id)}


# ─── Test & Health Endpoints ─────────────────────────────────────────────────

@router.post("/test", response_model=TestProviderResponse)
async def test_provider_connection(
    req: TestProviderRequest,
) -> TestProviderResponse:
    """Test connection to a provider without saving it."""
    import time

    start = time.monotonic()

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {"Content-Type": "application/json"}
            if req.api_key:
                headers["Authorization"] = f"Bearer {req.api_key}"

            # Try to list models (OpenAI-compatible endpoint)
            base_url = req.base_url.rstrip("/")

            if req.provider_type == "ollama":
                # Ollama uses /api/tags for models
                resp = await client.get(
                    f"{base_url}/api/tags",
                    headers=headers,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    models = [m.get("name", m.get("model", "")) for m in data.get("models", [])]
                    latency = int((time.monotonic() - start) * 1000)
                    return TestProviderResponse(
                        success=True,
                        latency_ms=latency,
                        message="Connected successfully",
                        models_available=models[:20] if models else None,
                    )
            else:
                # OpenAI-compatible /models endpoint
                resp = await client.get(
                    f"{base_url}/v1/models",
                    headers=headers,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    models = [m.get("id", "") for m in data.get("data", [])]
                    latency = int((time.monotonic() - start) * 1000)
                    return TestProviderResponse(
                        success=True,
                        latency_ms=latency,
                        message="Connected successfully",
                        models_available=models[:20] if models else None,
                    )
                elif resp.status_code == 404:
                    # Some providers don't have /models, try a simple completion
                    test_resp = await client.post(
                        f"{base_url}/v1/chat/completions",
                        headers=headers,
                        json={
                            "model": req.model,
                            "messages": [{"role": "user", "content": "Hi"}],
                            "max_tokens": 5,
                        },
                    )
                    if test_resp.status_code == 200:
                        latency = int((time.monotonic() - start) * 1000)
                        return TestProviderResponse(
                            success=True,
                            latency_ms=latency,
                            message="Connected (test completion succeeded)",
                        )

            latency = int((time.monotonic() - start) * 1000)
            return TestProviderResponse(
                success=False,
                latency_ms=latency,
                message=f"Connection failed: HTTP {resp.status_code}",
            )

    except httpx.TimeoutException:
        latency = int((time.monotonic() - start) * 1000)
        return TestProviderResponse(
            success=False,
            latency_ms=latency,
            message="Connection timeout (30s)",
        )
    except Exception as e:
        latency = int((time.monotonic() - start) * 1000)
        return TestProviderResponse(
            success=False,
            latency_ms=latency,
            message=f"Connection error: {str(e)}",
        )


@router.post("/{provider_id}/test", response_model=TestProviderResponse)
async def test_saved_provider(
    provider_id: uuid.UUID,
    user: User = Depends(get_current_user),
) -> TestProviderResponse:
    """Test a saved provider and update its health status."""
    from app.db.session import async_session_factory
    from app.models.llm_provider import UserLLMProvider
    from sqlalchemy import select
    import time

    async with async_session_factory() as db:
        stmt = select(UserLLMProvider).where(
            UserLLMProvider.id == provider_id,
            UserLLMProvider.user_id == user.id,
        )
        result = await db.execute(stmt)
        provider = result.scalar_one_or_none()

        if not provider:
            raise HTTPException(status_code=404, detail="Provider not found")

        # Run test
        api_key = decrypt_value(provider.api_key_encrypted)

        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                headers = {"Content-Type": "application/json"}
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"

                base_url = provider.base_url

                # Simple test request
                if provider.provider_type == "ollama":
                    resp = await client.get(f"{base_url}/api/tags", headers=headers)
                else:
                    resp = await client.get(f"{base_url}/v1/models", headers=headers)

                latency = int((time.monotonic() - start) * 1000)

                if resp.status_code == 200:
                    provider.health_status = "healthy"
                    provider.health_message = "Connected successfully"
                    provider.latency_ms = latency
                    provider.last_tested_at = datetime.utcnow()
                    await db.commit()

                    return TestProviderResponse(
                        success=True,
                        latency_ms=latency,
                        message="Connected successfully",
                    )
                else:
                    provider.health_status = "error"
                    provider.health_message = f"HTTP {resp.status_code}"
                    provider.latency_ms = latency
                    provider.last_tested_at = datetime.utcnow()
                    await db.commit()

                    return TestProviderResponse(
                        success=False,
                        latency_ms=latency,
                        message=f"HTTP {resp.status_code}",
                    )

        except Exception as e:
            latency = int((time.monotonic() - start) * 1000)
            provider.health_status = "error"
            provider.health_message = str(e)[:200]
            provider.latency_ms = latency
            provider.last_tested_at = datetime.utcnow()
            await db.commit()

            return TestProviderResponse(
                success=False,
                latency_ms=latency,
                message=str(e),
            )


# ─── Model Routing ───────────────────────────────────────────────────────────

@router.get("/models/available")
async def get_available_models(
    user: User = Depends(get_current_user),
) -> dict:
    """Get all available models from all user's providers."""
    from app.db.session import async_session_factory
    from app.models.llm_provider import UserLLMProvider
    from sqlalchemy import select

    async with async_session_factory() as db:
        stmt = (
            select(UserLLMProvider)
            .where(UserLLMProvider.user_id == user.id, UserLLMProvider.is_active)
        )
        result = await db.execute(stmt)
        providers = result.scalars().all()

        all_models = []
        for provider in providers:
            for model in provider.available_models:
                all_models.append({
                    "id": f"{provider.id}:{model}",
                    "provider_id": str(provider.id),
                    "provider_name": provider.name,
                    "model": model,
                    "provider_type": provider.provider_type,
                    "health_status": provider.health_status,
                })

        return {
            "models": all_models,
            "default_provider": str(next((p.id for p in providers if p.is_default), None)),
        }
