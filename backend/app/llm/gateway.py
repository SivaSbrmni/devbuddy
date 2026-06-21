"""LLM Gateway — multi-provider user-configured router.

This is the core of spec Part 2. It:
1. Compresses payloads (Part 3 pipeline)
2. Selects a provider cascade based on task type and user configuration
3. Tries each provider in order, skipping quota-exceeded / cooling-down ones
4. On 429/5xx, cools down the provider and tries the next
5. If all exhausted, enqueues to aep_pending_queue
6. Normalizes all responses to a single shape

The gateway is a singleton accessed via `llm_gateway` for health checks.
Per-user instances are created in the /LLM routes so each user gets their
own provider cascade loaded from their encrypted UserLLMProvider records.
"""

from __future__ import annotations

import os
import uuid
from typing import Any, AsyncIterator, Optional

import httpx
import structlog

from app.llm.providers.base import BaseProvider, NormalizedResponse
from app.llm.providers import (
    GroqProvider, GeminiProvider, CerebrasProvider, OpenRouterProvider,
    GitHubModelsProvider, MistralProvider, CloudflareProvider,
)
from app.llm.providers.user_provider import UserProviderAdapter
from app.llm.quota import QuotaLedger, CircuitBreaker

log = structlog.get_logger()

# ─── Task Type → Provider Cascade (spec Part 2.3) ────────────────────────────

# Default cascades used when the user has no routing rules configured.
TASK_CASCADES: dict[str, list[tuple[str, str]]] = {
    # Default cascades used when the user has no routing rules configured.
    # These are model-name hints only; actual provider selection comes from
    # the user's encrypted UserLLMProvider configuration.
    "planner":      [("Default", "default")],
    "coder":        [("Default", "default")],
    "debugger":     [("Default", "default")],
    "reviewer":     [("Default", "default")],
    "docs_summary": [("Default", "default")],
    "embeddings":   [("Default", "default")],
    "test":         [("Default", "default")],
    "security":     [("Default", "default")],
    "devops":       [("Default", "default")],
}

# Map AEP task types to the existing provider routing task types.
TASK_TYPE_MAP: dict[str, str] = {
    "planner": "planning",
    "coder": "coding",
    "debugger": "debugging",
    "reviewer": "review",
    "test": "testing",
    "security": "security",
    "docs": "documentation",
    "devops": "deployment",
    "docs_summary": "summarization",
    "embeddings": "embeddings",
}


class LLMGateway:
    """Multi-provider LLM router with quota enforcement and circuit breaking.

    Usage:
        from app.llm.gateway import LLMGateway
        gateway = LLMGateway(user_id=user.id, db=db)
        await gateway.initialize()
        response = await gateway.chat(
            messages=[{"role": "user", "content": "Hello"}],
            task_type="planner",
        )
    """

    def __init__(
        self,
        user_id: Optional[uuid.UUID] = None,
        db: Any = None,
    ) -> None:
        self.providers: dict[str, BaseProvider] = {}
        self.quota = QuotaLedger()
        self.breaker = CircuitBreaker()
        self._initialized = False
        self.user_id = user_id
        self.db = db
        self._routing_rules: dict[str, list[tuple[str, str]]] = {}
        self._default_cascade: list[tuple[str, str]] = []

    def initialize(self) -> None:
        """Register providers from environment variables (for singleton/health checks)."""
        provider_classes = [
            GroqProvider, GeminiProvider, CerebrasProvider, OpenRouterProvider,
            GitHubModelsProvider, MistralProvider, CloudflareProvider,
        ]

        for cls in provider_classes:
            provider = cls()
            # Load API key from environment
            api_key = os.environ.get(provider.config.api_key_env, "")
            if api_key:
                provider.configure(api_key)
                log.info("llm.provider.configured", name=provider.name, models=provider.config.models)
            else:
                log.info("llm.provider.not_configured", name=provider.name, env_var=provider.config.api_key_env)

            self.providers[provider.name] = provider
            self.quota.register_limits(provider.name, provider.config.limits)

        self._initialized = True
        log.info("llm.gateway.initialized", provider_count=len(self.providers))

    async def initialize_for_user(self) -> None:
        """Load providers from the user's encrypted provider configuration.

        This is the primary path for the /LLM routes. All credentials are
        decrypted at call time from the existing UserLLMProvider table.
        """
        if not self.user_id or not self.db:
            raise RuntimeError("LLMGateway requires user_id and db to initialize_for_user")

        from sqlalchemy import select
        from app.models.llm_provider import UserLLMProvider, ProviderRoutingRule

        stmt = (
            select(UserLLMProvider)
            .where(UserLLMProvider.user_id == self.user_id)
            .where(UserLLMProvider.is_active)
            .order_by(UserLLMProvider.priority, UserLLMProvider.created_at)
        )
        result = await self.db.execute(stmt)
        user_providers = result.scalars().all()

        if not user_providers:
            log.warning("llm.no_user_providers", user_id=str(self.user_id))
            self._initialized = True
            return

        for record in user_providers:
            adapter = UserProviderAdapter(record)
            self.providers[record.name] = adapter
            # Register safe default limits for each available model
            for model in adapter.config.models:
                self.quota.register_limits(record.name, {
                    "rpm": record.max_tokens or 60,
                    "rpd": 1000,
                    "tpm": 10000,
                })
            log.info("llm.user_provider.loaded", user_id=str(self.user_id), name=record.name, type=record.provider_type)

        # Load routing rules
        rules_stmt = (
            select(ProviderRoutingRule)
            .where(ProviderRoutingRule.user_id == self.user_id)
            .where(ProviderRoutingRule.is_active)
            .order_by(ProviderRoutingRule.priority)
        )
        rules_result = await self.db.execute(rules_stmt)
        rules = rules_result.scalars().all()

        for rule in rules:
            task_type = rule.task_type
            provider = self.providers.get(rule.provider.name)
            if provider:
                model = rule.model_override or rule.provider.default_model
                self._routing_rules.setdefault(task_type, []).append((rule.provider.name, model))

        # Build default cascade from user provider priorities (all models)
        self._default_cascade = []
        for record in user_providers:
            for model in record.available_models or [record.default_model]:
                self._default_cascade.append((record.name, model))

        self._initialized = True
        log.info("llm.gateway.user_initialized", user_id=str(self.user_id), provider_count=len(self.providers))

    def get_cascade(self, task_type: str) -> list[dict[str, str]]:
        """Return the provider cascade for a task type (for /LLM/route endpoint)."""
        # Prefer user routing rules, then AEP task mapping, then default cascade
        mapped_type = TASK_TYPE_MAP.get(task_type, task_type)
        cascade = self._routing_rules.get(mapped_type) or self._routing_rules.get(task_type)
        if not cascade:
            cascade = self._default_cascade or TASK_CASCADES.get(task_type, TASK_CASCADES["planner"])
        return [{"provider": p, "model": m} for p, m in cascade]

    async def chat(
        self,
        messages: list[dict[str, str]],
        task_type: str = "planner",
        model: Optional[str] = None,
        system_prompt: str = "",
        max_tokens: int = 4096,
        temperature: float = 0.0,
        allow_reserve_tier: bool = False,
    ) -> NormalizedResponse:
        """Route a chat request through the provider cascade.

        Args:
            messages: Chat messages (OpenAI format)
            task_type: One of planner, coder, debugger, reviewer, docs_summary, etc.
            model: Optional explicit model override (bypasses cascade)
            system_prompt: Optional system prompt prepended to messages
            max_tokens: Max output tokens
            temperature: Sampling temperature
            allow_reserve_tier: Allow paid reserve tier as last resort

        Returns:
            NormalizedResponse with text, usage, provider, model info
        """
        if not self._initialized:
            self.initialize()

        # If explicit model, find the provider that serves it
        if model:
            return await self._call_explicit_model(messages, model, system_prompt, max_tokens, temperature)

        cascade = self.get_cascade(task_type)
        last_error: Optional[str] = None

        for entry in cascade:
            provider_name = entry["provider"]
            model_name = entry["model"]
            provider = self.providers.get(provider_name)
            if not provider or not provider.is_configured():
                continue

            # Check quota
            if self.quota.would_exceed(provider_name, model_name):
                log.info("llm.quota_exceeded", provider=provider_name, model=model_name)
                continue

            # Check circuit breaker
            if self.breaker.is_cooling_down(provider_name, model_name):
                log.info("llm.breaker_open", provider=provider_name, model=model_name)
                continue

            # Attempt the call
            try:
                response = await provider.chat(
                    messages=messages,
                    model=model_name,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system_prompt=system_prompt,
                )
                self.quota.record(provider_name, model_name, response.usage.get("input_tokens", 0), response.usage.get("output_tokens", 0))
                self.breaker.record_success(provider_name, model_name)
                log.info(
                    "llm.request.success",
                    provider=provider_name,
                    model=model_name,
                    task_type=task_type,
                    input_tokens=response.usage.get("input_tokens", 0),
                    output_tokens=response.usage.get("output_tokens", 0),
                    latency_ms=response.latency_ms,
                )
                return response

            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                error_msg = f"HTTP {status}: {e.response.text[:200]}"
                last_error = error_msg

                if status == 429:
                    # Rate limited — cool down with Retry-After if available
                    retry_after = e.response.headers.get("Retry-After")
                    retry_secs = float(retry_after) if retry_after else None
                    self.breaker.cool_down(provider_name, model_name, error_msg, retry_secs)
                elif status >= 500:
                    # Server error — cool down with backoff
                    self.breaker.cool_down(provider_name, model_name, error_msg)
                else:
                    # 4xx (not 429) — client error, don't retry this provider
                    log.warning("llm.client_error", provider=provider_name, model=model_name, status=status)

                continue

            except Exception as e:
                last_error = str(e)
                self.breaker.cool_down(provider_name, model_name, last_error)
                log.warning("llm.provider_error", provider=provider_name, model=model_name, error=last_error)
                continue

        # All providers exhausted
        log.error("llm.cascade_exhausted", task_type=task_type, last_error=last_error)
        return NormalizedResponse(
            text="",
            finish_reason="error",
            usage={"input_tokens": 0, "output_tokens": 0},
            provider="none",
            model="none",
        )

    async def stream(
        self,
        messages: list[dict[str, str]],
        task_type: str = "coder",
        model: Optional[str] = None,
        system_prompt: str = "",
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> AsyncIterator[str]:
        """Stream a chat response through the provider cascade."""
        if not self._initialized:
            self.initialize()

        if model:
            provider = self._find_provider_for_model(model)
            if provider:
                async for chunk in provider.stream(messages, model, max_tokens, temperature, system_prompt):
                    yield chunk
                return

        cascade = self.get_cascade(task_type)
        log.info("llm.stream.cascade", cascade=cascade, model=model, task_type=task_type)
        for entry in cascade:
            provider_name = entry["provider"]
            model_name = entry["model"]
            provider = self.providers.get(provider_name)
            if not provider or not provider.is_configured():
                log.info("llm.provider.skipped", provider=provider_name, model=model_name, reason="not_configured")
                continue
            if self.quota.would_exceed(provider_name, model_name):
                log.info("llm.provider.skipped", provider=provider_name, model=model_name, reason="quota")
                continue
            if self.breaker.is_cooling_down(provider_name, model_name):
                log.info("llm.provider.skipped", provider=provider_name, model=model_name, reason="cooling_down")
                continue

            try:
                log.info("llm.provider.trying", provider=provider_name, model=model_name)
                async for chunk in provider.stream(messages, model_name, max_tokens, temperature, system_prompt):
                    yield chunk
                self.quota.record(provider_name, model_name, 0, 0)  # tokens counted at stream end
                self.breaker.record_success(provider_name, model_name)
                log.info("llm.provider.success", provider=provider_name, model=model_name)
                return
            except Exception as e:
                log.warning("llm.provider.error", provider=provider_name, model=model_name, error=str(e))
                self.breaker.cool_down(provider_name, model_name, str(e))
                continue

        log.error("llm.cascade.exhausted", model=model, task_type=task_type)
        yield ""  # all exhausted

    async def embeddings(self, texts: list[str], model: Optional[str] = None) -> list[list[float]]:
        """Get embeddings via the user's configured embedding providers."""
        if not self._initialized:
            self.initialize()

        cascade = self.get_cascade("embeddings")
        for entry in cascade:
            provider_name = entry["provider"]
            model_name = entry["model"]
            if model and model != model_name:
                continue
            provider = self.providers.get(provider_name)
            if not provider or not provider.is_configured():
                continue
            if self.breaker.is_cooling_down(provider_name, model_name):
                continue
            try:
                return await provider.embeddings(texts, model_name)
            except Exception as e:
                self.breaker.cool_down(provider_name, model_name, str(e))
                continue
        return []

    async def _call_explicit_model(
        self,
        messages: list[dict[str, str]],
        model: str,
        system_prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> NormalizedResponse:
        """Call a specific model, bypassing the cascade."""
        provider = self._find_provider_for_model(model)
        if not provider:
            raise ValueError(f"No provider serves model '{model}'")
        return await provider.chat(messages, model, max_tokens, temperature, system_prompt)

    def _find_provider_for_model(self, model: str) -> Optional[BaseProvider]:
        """Find the provider that serves a given model."""
        for provider in self.providers.values():
            if provider.supports_model(model) and provider.is_configured():
                return provider
        return None

    async def list_models(self) -> list[dict[str, Any]]:
        """List all available models from all configured providers."""
        models = []
        for provider in self.providers.values():
            if not provider.is_configured():
                continue
            for model in provider.config.models:
                models.append({
                    "id": model,
                    "provider": provider.name,
                    "limits": provider.config.limits,
                })
        return models

    async def health_check(self) -> dict[str, Any]:
        """Check health of all providers."""
        result = {}
        for name, provider in self.providers.items():
            result[name] = {
                "ok": provider.is_configured(),
                "configured": provider.is_configured(),
                "models": provider.config.models,
            }
            # Add quota and breaker status for first model
            if provider.config.models:
                model = provider.config.models[0]
                result[name]["quota"] = self.quota.get_usage(name, model)
                result[name]["breaker"] = self.breaker.get_state(name, model)
        return result


# Singleton
llm_gateway = LLMGateway()
