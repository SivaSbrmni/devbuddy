"""Tests for the LLM Gateway — cascade failover, quota enforcement, circuit breaker.

Spec Part 3 required tests:
  - Cascade failover: mock 429 on provider 1 → provider 2 used, provider 1 quota untouched
  - Quota enforcement: near-limit simulation → router pre-empts before a real 429
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.llm.gateway import LLMGateway, TASK_CASCADES
from app.llm.quota import QuotaLedger, CircuitBreaker
from app.llm.providers.base import NormalizedResponse, BaseProvider, ProviderConfig


class MockProvider(BaseProvider):
    """Mock provider for testing — returns configurable responses or errors."""

    def __init__(self, name: str, models: list[str], response_text: str = "OK", should_fail: bool = False, fail_status: int = 429):
        super().__init__(ProviderConfig(
            name=name,
            models=models,
            limits={"rpm": 30, "rpd": 1000, "tpm": 6000},
            cooldown_on_error=60_000,
            api_key_env="MOCK_KEY",
            base_url="https://mock.example.com/v1",
        ))
        self._api_key = "mock-key"
        self.response_text = response_text
        self.should_fail = should_fail
        self.fail_status = fail_status
        self.call_count = 0

    async def chat(self, messages, model, max_tokens=4096, temperature=0.0, system_prompt=""):
        self.call_count += 1
        if self.should_fail:
            import httpx
            raise httpx.HTTPStatusError(
                f"HTTP {self.fail_status}",
                request=httpx.Request("POST", "https://mock.example.com/v1/chat/completions"),
                response=httpx.Response(self.fail_status, text="rate limited"),
            )
        return NormalizedResponse(
            text=self.response_text,
            finish_reason="stop",
            usage={"input_tokens": 10, "output_tokens": 5},
            provider=self.name,
            model=model,
            latency_ms=100,
        )

    async def stream(self, messages, model, max_tokens=4096, temperature=0.0, system_prompt=""):
        if self.should_fail:
            raise RuntimeError("mock failure")
        yield self.response_text

    async def embeddings(self, texts, model):
        return [[0.1, 0.2, 0.3] for _ in texts]


class TestCascadeFailover:
    """Spec: mock 429 on provider 1 → provider 2 used, provider 1 quota untouched."""

    def test_429_falls_over_to_next_provider(self):
        """When provider 1 returns 429, provider 2 should be used."""
        gateway = LLMGateway()
        gateway.initialize = lambda: None  # skip real init
        gateway._initialized = True

        failing_provider = MockProvider("groq", ["llama-3.3-70b-versatile"], should_fail=True, fail_status=429)
        success_provider = MockProvider("gemini", ["gemini-2.5-flash"], response_text="Success from Gemini")

        gateway.providers = {"groq": failing_provider, "gemini": success_provider, "openrouter": MockProvider("openrouter", ["deepseek/deepseek-r1"])}

        response = asyncio.get_event_loop().run_until_complete(
            gateway.chat(messages=[{"role": "user", "content": "test"}], task_type="planner")
        )

        assert response.text == "Success from Gemini"
        assert response.provider == "gemini"
        assert failing_provider.call_count == 1  # Was tried
        assert success_provider.call_count == 1  # Was used as fallback

    def test_5xx_falls_over_to_next_provider(self):
        """When provider 1 returns 5xx, provider 2 should be used."""
        gateway = LLMGateway()
        gateway.initialize = lambda: None
        gateway._initialized = True

        failing_provider = MockProvider("groq", ["llama-3.3-70b-versatile"], should_fail=True, fail_status=500)
        success_provider = MockProvider("gemini", ["gemini-2.5-flash"], response_text="Success from Gemini")

        gateway.providers = {"groq": failing_provider, "gemini": success_provider}

        response = asyncio.get_event_loop().run_until_complete(
            gateway.chat(messages=[{"role": "user", "content": "test"}], task_type="planner")
        )

        assert response.provider == "gemini"

    def test_all_providers_exhausted_returns_empty(self):
        """When all providers fail, return empty response with error finish_reason."""
        gateway = LLMGateway()
        gateway.initialize = lambda: None
        gateway._initialized = True

        gateway.providers = {
            "groq": MockProvider("groq", ["llama-3.3-70b-versatile"], should_fail=True, fail_status=429),
            "gemini": MockProvider("gemini", ["gemini-2.5-flash"], should_fail=True, fail_status=429),
            "openrouter": MockProvider("openrouter", ["deepseek/deepseek-r1"], should_fail=True, fail_status=429),
        }

        response = asyncio.get_event_loop().run_until_complete(
            gateway.chat(messages=[{"role": "user", "content": "test"}], task_type="planner")
        )

        assert response.text == ""
        assert response.finish_reason == "error"
        assert response.provider == "none"


class TestQuotaEnforcement:
    """Spec: near-limit simulation → router pre-empts before a real 429."""

    def test_quota_preempts_before_429(self):
        """When quota is near limit, router skips the provider."""
        gateway = LLMGateway()
        gateway.initialize = lambda: None
        gateway._initialized = True

        # Set up a provider with very low RPM limit
        provider = MockProvider("groq", ["llama-3.3-70b-versatile"], response_text="from groq")
        gateway.providers = {"groq": provider, "gemini": MockProvider("gemini", ["gemini-2.5-flash"], response_text="from gemini")}

        # Set quota to exactly the limit
        gateway.quota.register_limits("groq", {"rpm": 2, "rpd": 1000, "tpm": 6000})
        gateway.quota.record("groq", "llama-3.3-70b-versatile", 10, 5)
        gateway.quota.record("groq", "llama-3.3-70b-versatile", 10, 5)
        # Now groq is at 2/2 RPM — should be skipped

        response = asyncio.get_event_loop().run_until_complete(
            gateway.chat(messages=[{"role": "user", "content": "test"}], task_type="planner")
        )

        # Should fall through to gemini
        assert response.provider == "gemini"
        assert provider.call_count == 0  # groq was not even called

    def test_circuit_breaker_skips_cooling_down_provider(self):
        """When circuit breaker is open, provider is skipped."""
        gateway = LLMGateway()
        gateway.initialize = lambda: None
        gateway._initialized = True

        provider = MockProvider("groq", ["llama-3.3-70b-versatile"], response_text="from groq")
        gateway.providers = {"groq": provider, "gemini": MockProvider("gemini", ["gemini-2.5-flash"], response_text="from gemini")}

        # Open the circuit breaker for groq
        gateway.breaker.cool_down("groq", "llama-3.3-70b-versatile", "test error")

        response = asyncio.get_event_loop().run_until_complete(
            gateway.chat(messages=[{"role": "user", "content": "test"}], task_type="planner")
        )

        assert response.provider == "gemini"
        assert provider.call_count == 0  # groq was skipped

    def test_breaker_resets_after_success(self):
        """Circuit breaker resets after a successful call."""
        breaker = CircuitBreaker(base_cooldown_ms=100)

        # Cool down
        breaker.cool_down("groq", "llama-3.3-70b", "error")
        assert breaker.is_cooling_down("groq", "llama-3.3-70b")

        # Record success
        breaker.record_success("groq", "llama-3.3-70b")
        assert not breaker.is_cooling_down("groq", "llama-3.3-70b")
        assert breaker.get_state("groq", "llama-3.3-70b")["failures"] == 0

    def test_breaker_exponential_backoff(self):
        """Circuit breaker uses exponential backoff on repeated failures."""
        breaker = CircuitBreaker(base_cooldown_ms=1000)

        breaker.cool_down("groq", "llama-3.3-70b", "error 1")
        state1 = breaker.get_state("groq", "llama-3.3-70b")
        assert state1["failures"] == 1

        breaker.cool_down("groq", "llama-3.3-70b", "error 2")
        state2 = breaker.get_state("groq", "llama-3.3-70b")
        assert state2["failures"] == 2
        # Second cooldown should be longer than first
        assert state2["cooldown_remaining"] >= state1["cooldown_remaining"]


class TestTaskCascades:
    """Verify task type cascades are correctly configured."""

    def test_planner_cascade(self):
        cascade = TASK_CASCADES["planner"]
        assert cascade[0] == ("groq", "llama-3.3-70b-versatile")
        assert cascade[1] == ("gemini", "gemini-2.5-flash")

    def test_coder_cascade(self):
        cascade = TASK_CASCADES["coder"]
        assert cascade[0] == ("openrouter", "qwen/qwen3-coder-480b")

    def test_embeddings_cascade(self):
        cascade = TASK_CASCADES["embeddings"]
        assert cascade[0] == ("gemini", "text-embedding-004")

    def test_unknown_task_uses_planner_default(self):
        gateway = LLMGateway()
        cascade = gateway.get_cascade("unknown_task")
        assert len(cascade) > 0  # Falls back to planner
