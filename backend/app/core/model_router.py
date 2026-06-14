"""Centralized Model Router — all LLM calls go through here.

Responsibilities:
- Provider selection based on task type
- Cost optimization (cheap models for drafts, Claude for engineering)
- Fallback chains
- Token budgeting
- Usage tracking
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import anthropic
import httpx
import structlog

from app.core.config import settings

log = structlog.get_logger()


class ModelTier(str, Enum):
    DRAFT = "draft"        # Llama — cheap, fast, good enough for scaffolding
    ENGINEER = "engineer"  # Claude — precision engineering, review, coding


class TaskCategory(str, Enum):
    # Llama-tier tasks
    REQUIREMENT_ANALYSIS = "requirement_analysis"
    PLANNING_DRAFT = "planning_draft"
    TASK_DECOMPOSITION = "task_decomposition"
    CONTEXT_COMPRESSION = "context_compression"
    WORKFLOW_ORCHESTRATION = "workflow_orchestration"
    SUMMARIZATION = "summarization"
    LOG_ANALYSIS = "log_analysis"
    STATUS_REPORTING = "status_reporting"

    # Claude-tier tasks
    REQUIREMENTS_REVIEW = "requirements_review"
    ARCHITECTURE_REVIEW = "architecture_review"
    SYSTEM_DESIGN = "system_design"
    DATABASE_DESIGN = "database_design"
    API_DESIGN = "api_design"
    CODING = "coding"
    CODE_REVIEW = "code_review"
    REFACTORING = "refactoring"
    SECURITY_REVIEW = "security_review"
    TEST_GENERATION = "test_generation"
    ROOT_CAUSE_ANALYSIS = "root_cause_analysis"
    DEBUGGING = "debugging"
    DEPLOYMENT_VALIDATION = "deployment_validation"
    FINAL_APPROVAL = "final_approval"


# Mapping: which tier handles which task category
TASK_TIER_MAP: dict[TaskCategory, ModelTier] = {
    TaskCategory.REQUIREMENT_ANALYSIS: ModelTier.DRAFT,
    TaskCategory.PLANNING_DRAFT: ModelTier.DRAFT,
    TaskCategory.TASK_DECOMPOSITION: ModelTier.DRAFT,
    TaskCategory.CONTEXT_COMPRESSION: ModelTier.DRAFT,
    TaskCategory.WORKFLOW_ORCHESTRATION: ModelTier.DRAFT,
    TaskCategory.SUMMARIZATION: ModelTier.DRAFT,
    TaskCategory.LOG_ANALYSIS: ModelTier.DRAFT,
    TaskCategory.STATUS_REPORTING: ModelTier.DRAFT,
    TaskCategory.REQUIREMENTS_REVIEW: ModelTier.ENGINEER,
    TaskCategory.ARCHITECTURE_REVIEW: ModelTier.ENGINEER,
    TaskCategory.SYSTEM_DESIGN: ModelTier.ENGINEER,
    TaskCategory.DATABASE_DESIGN: ModelTier.ENGINEER,
    TaskCategory.API_DESIGN: ModelTier.ENGINEER,
    TaskCategory.CODING: ModelTier.ENGINEER,
    TaskCategory.CODE_REVIEW: ModelTier.ENGINEER,
    TaskCategory.REFACTORING: ModelTier.ENGINEER,
    TaskCategory.SECURITY_REVIEW: ModelTier.ENGINEER,
    TaskCategory.TEST_GENERATION: ModelTier.ENGINEER,
    TaskCategory.ROOT_CAUSE_ANALYSIS: ModelTier.ENGINEER,
    TaskCategory.DEBUGGING: ModelTier.ENGINEER,
    TaskCategory.DEPLOYMENT_VALIDATION: ModelTier.ENGINEER,
    TaskCategory.FINAL_APPROVAL: ModelTier.ENGINEER,
}


@dataclass
class LLMResponse:
    content: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    cost_usd: float
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class LLMRequest:
    messages: list[dict[str, str]]
    task_category: TaskCategory
    system_prompt: str = ""
    max_tokens: int = 4096
    temperature: float = 0.0
    project_id: str | None = None
    task_id: str | None = None
    model: str | None = None  # Per-request model override
    provider: str | None = None  # Per-request provider override


# Rough cost estimates per 1M tokens
COST_TABLE = {
    "anthropic": {"input": 3.0, "output": 15.0},
    "llama": {"input": 0.05, "output": 0.08},
    "ollama": {"input": 0.0, "output": 0.0},  # Ollama cloud free tier
}


def _estimate_cost(provider: str, input_tokens: int, output_tokens: int) -> float:
    rates = COST_TABLE.get(provider, {"input": 0.0, "output": 0.0})
    return (input_tokens * rates["input"] + output_tokens * rates["output"]) / 1_000_000


class ModelRouter:
    """Singleton-style router. Instantiated once at app startup."""

    def __init__(self) -> None:
        self._anthropic: anthropic.AsyncAnthropic | None = None
        self._llama_client: httpx.AsyncClient | None = None
        self._ollama_client: httpx.AsyncClient | None = None

    async def startup(self) -> None:
        if settings.ANTHROPIC_API_KEY:
            self._anthropic = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        if settings.LLAMA_API_KEY:
            self._llama_client = httpx.AsyncClient(
                base_url=settings.LLAMA_API_BASE,
                headers={"Authorization": f"Bearer {settings.LLAMA_API_KEY}"},
                timeout=120.0,
            )
        if settings.OLLAMA_API_KEY:
            self._ollama_client = httpx.AsyncClient(
                base_url=settings.OLLAMA_API_BASE,
                headers={"Authorization": f"Bearer {settings.OLLAMA_API_KEY}"},
                timeout=120.0,
                follow_redirects=True,
            )

    async def shutdown(self) -> None:
        if self._llama_client:
            await self._llama_client.aclose()
        if self._ollama_client:
            await self._ollama_client.aclose()

    def _select_tier(self, category: TaskCategory) -> ModelTier:
        return TASK_TIER_MAP.get(category, ModelTier.ENGINEER)

    async def complete(self, request: LLMRequest) -> LLMResponse:
        # If provider/model specified, bypass tier routing
        if request.provider:
            log.info("model_router.override", provider=request.provider, model=request.model)
            return await self._call_provider(request, request.provider)
        
        tier = self._select_tier(request.task_category)
        log.info("model_router.routing", tier=tier.value, category=request.task_category.value)

        if tier == ModelTier.ENGINEER:
            return await self._call_with_fallback(request, primary="anthropic", fallback="ollama")
        return await self._call_with_fallback(request, primary="ollama", fallback="anthropic")

    async def _call_with_fallback(
        self, request: LLMRequest, *, primary: str, fallback: str
    ) -> LLMResponse:
        try:
            return await self._call_provider(request, primary)
        except Exception as exc:
            log.warning("model_router.primary_failed", provider=primary, error=str(exc))
            try:
                return await self._call_provider(request, fallback)
            except Exception as fallback_exc:
                raise RuntimeError(
                    f"No LLM provider available. Primary ({primary}): {exc}. "
                    f"Fallback ({fallback}): {fallback_exc}. "
                    "Configure ANTHROPIC_API_KEY or LLAMA_API_KEY in environment."
                ) from fallback_exc

    async def _call_provider(self, request: LLMRequest, provider: str) -> LLMResponse:
        if provider == "anthropic":
            return await self._call_anthropic(request)
        if provider == "llama":
            return await self._call_llama(request)
        if provider == "ollama":
            return await self._call_ollama(request)
        raise ValueError(f"Unknown provider: {provider}")

    async def _call_provider_stream(self, request: LLMRequest, provider: str):
        """Yield text deltas for streaming responses."""
        if provider == "anthropic":
            async for delta in self._call_anthropic_stream(request):
                yield delta
        elif provider == "ollama":
            async for delta in self._call_ollama_stream(request):
                yield delta
        else:
            raise ValueError(f"Streaming not supported for provider: {provider}")

    async def _call_anthropic(self, request: LLMRequest) -> LLMResponse:
        if not self._anthropic:
            raise RuntimeError("Anthropic client not configured")

        start = time.monotonic()
        model = request.model or settings.ANTHROPIC_MODEL
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": min(request.max_tokens, settings.MAX_TOKENS_PER_REQUEST),
            "messages": request.messages,
            "temperature": request.temperature,
        }
        if request.system_prompt:
            kwargs["system"] = request.system_prompt

        resp = await self._anthropic.messages.create(**kwargs)
        latency = int((time.monotonic() - start) * 1000)
        content = resp.content[0].text if resp.content else ""
        input_tok = resp.usage.input_tokens
        output_tok = resp.usage.output_tokens

        return LLMResponse(
            content=content,
            provider="anthropic",
            model=model,
            input_tokens=input_tok,
            output_tokens=output_tok,
            latency_ms=latency,
            cost_usd=_estimate_cost("anthropic", input_tok, output_tok),
        )

    async def _call_anthropic_stream(self, request: LLMRequest):
        """Stream Anthropic responses, yielding text deltas."""
        if not self._anthropic:
            raise RuntimeError("Anthropic client not configured")

        model = request.model or settings.ANTHROPIC_MODEL
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": min(request.max_tokens, settings.MAX_TOKENS_PER_REQUEST),
            "messages": request.messages,
            "temperature": request.temperature,
            "stream": True,
        }
        if request.system_prompt:
            kwargs["system"] = request.system_prompt

        async with self._anthropic.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield text

    async def _call_llama(self, request: LLMRequest) -> LLMResponse:
        if not self._llama_client:
            raise RuntimeError("Llama client not configured")

        messages: list[dict[str, str]] = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.extend(request.messages)

        start = time.monotonic()
        resp = await self._llama_client.post(
            "/chat/completions",
            json={
                "model": settings.LLAMA_MODEL,
                "messages": messages,
                "max_tokens": min(request.max_tokens, settings.MAX_TOKENS_PER_REQUEST),
                "temperature": request.temperature,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        latency = int((time.monotonic() - start) * 1000)

        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        input_tok = usage.get("prompt_tokens", 0)
        output_tok = usage.get("completion_tokens", 0)

        return LLMResponse(
            content=content,
            provider="llama",
            model=settings.LLAMA_MODEL,
            input_tokens=input_tok,
            output_tokens=output_tok,
            latency_ms=latency,
            cost_usd=_estimate_cost("llama", input_tok, output_tok),
        )


    async def _call_ollama(self, request: LLMRequest) -> LLMResponse:
        if not self._ollama_client:
            raise RuntimeError("Ollama client not configured")

        messages: list[dict[str, str]] = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.extend(request.messages)

        start = time.monotonic()
        model = request.model or settings.OLLAMA_MODEL
        resp = await self._ollama_client.post(
            "/chat/completions",
            json={
                "model": model,
                "messages": messages,
                "stream": False,
                "max_tokens": min(request.max_tokens, settings.MAX_TOKENS_PER_REQUEST),
                "temperature": request.temperature,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        latency = int((time.monotonic() - start) * 1000)

        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        input_tok = usage.get("prompt_tokens", 0)
        output_tok = usage.get("completion_tokens", 0)

        return LLMResponse(
            content=content,
            provider="ollama",
            model=model,
            input_tokens=input_tok,
            output_tokens=output_tok,
            latency_ms=latency,
            cost_usd=_estimate_cost("ollama", input_tok, output_tok),
        )

    async def _call_ollama_stream(self, request: LLMRequest):
        """Stream Ollama responses, yielding text deltas."""
        if not self._ollama_client:
            raise RuntimeError("Ollama client not configured")

        messages: list[dict[str, str]] = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.extend(request.messages)

        model = request.model or settings.OLLAMA_MODEL
        async with self._ollama_client.stream(
            "POST",
            "/chat/completions",
            json={
                "model": model,
                "messages": messages,
                "stream": True,
                "max_tokens": min(request.max_tokens, settings.MAX_TOKENS_PER_REQUEST),
                "temperature": request.temperature,
            },
            timeout=120.0,
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line:
                    continue
                try:
                    if line.startswith("data: "):
                        line = line[6:]
                    if line == "[DONE]":
                        break
                    data = json.loads(line)
                    if "choices" in data and len(data["choices"]) > 0:
                        delta = data["choices"][0].get("delta", {})
                        if "content" in delta:
                            yield delta["content"]
                except json.JSONDecodeError:
                    continue


# Singleton
model_router = ModelRouter()
