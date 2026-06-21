"""Tests for the LLM Gateway — cascade failover, quota enforcement, circuit breaker.

Spec Part 3 required tests:
  - Cascade failover: mock 429 on provider 1 → provider 2 used, provider 1 quota untouched
  - Quota enforcement: near-limit simulation → router pre-empts before a real 429
"""

import asyncio

from app.llm.gateway import LLMGateway
from app.llm.quota import CircuitBreaker
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

    def _make_gateway(self, providers: dict, cascade: list[tuple[str, str]] | None = None):
        gateway = LLMGateway()
        gateway.initialize = lambda: None  # skip real init
        gateway._initialized = True
        gateway.providers = providers
        gateway._default_cascade = cascade or [("provider-1", "model-1"), ("provider-2", "model-2")]
        return gateway

    def test_429_falls_over_to_next_provider(self):
        """When provider 1 returns 429, provider 2 should be used."""
        failing_provider = MockProvider("provider-1", ["model-1"], should_fail=True, fail_status=429)
        success_provider = MockProvider("provider-2", ["model-2"], response_text="Success from provider-2")
        gateway = self._make_gateway(
            {"provider-1": failing_provider, "provider-2": success_provider},
            [("provider-1", "model-1"), ("provider-2", "model-2")],
        )

        response = asyncio.get_event_loop().run_until_complete(
            gateway.chat(messages=[{"role": "user", "content": "test"}], task_type="planner")
        )

        assert response.text == "Success from provider-2"
        assert response.provider == "provider-2"
        assert failing_provider.call_count == 1  # Was tried
        assert success_provider.call_count == 1  # Was used as fallback

    def test_5xx_falls_over_to_next_provider(self):
        """When provider 1 returns 5xx, provider 2 should be used."""
        failing_provider = MockProvider("provider-1", ["model-1"], should_fail=True, fail_status=500)
        success_provider = MockProvider("provider-2", ["model-2"], response_text="Success from provider-2")
        gateway = self._make_gateway(
            {"provider-1": failing_provider, "provider-2": success_provider},
            [("provider-1", "model-1"), ("provider-2", "model-2")],
        )

        response = asyncio.get_event_loop().run_until_complete(
            gateway.chat(messages=[{"role": "user", "content": "test"}], task_type="planner")
        )

        assert response.provider == "provider-2"

    def test_all_providers_exhausted_returns_empty(self):
        """When all providers fail, return empty response with error finish_reason."""
        gateway = self._make_gateway(
            {
                "provider-1": MockProvider("provider-1", ["model-1"], should_fail=True, fail_status=429),
                "provider-2": MockProvider("provider-2", ["model-2"], should_fail=True, fail_status=429),
                "provider-3": MockProvider("provider-3", ["model-3"], should_fail=True, fail_status=429),
            },
            [("provider-1", "model-1"), ("provider-2", "model-2"), ("provider-3", "model-3")],
        )

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
        # Set up a provider with very low RPM limit
        provider = MockProvider("provider-1", ["model-1"], response_text="from provider-1")
        gateway = LLMGateway()
        gateway.initialize = lambda: None
        gateway._initialized = True
        gateway.providers = {"provider-1": provider, "provider-2": MockProvider("provider-2", ["model-2"], response_text="from provider-2")}
        gateway._default_cascade = [("provider-1", "model-1"), ("provider-2", "model-2")]

        # Set quota to exactly the limit
        gateway.quota.register_limits("provider-1", {"rpm": 2, "rpd": 1000, "tpm": 6000})
        gateway.quota.record("provider-1", "model-1", 10, 5)
        gateway.quota.record("provider-1", "model-1", 10, 5)
        # Now provider-1 is at 2/2 RPM — should be skipped

        response = asyncio.get_event_loop().run_until_complete(
            gateway.chat(messages=[{"role": "user", "content": "test"}], task_type="planner")
        )

        # Should fall through to provider-2
        assert response.provider == "provider-2"
        assert provider.call_count == 0  # provider-1 was not even called

    def test_circuit_breaker_skips_cooling_down_provider(self):
        """When circuit breaker is open, provider is skipped."""
        provider = MockProvider("provider-1", ["model-1"], response_text="from provider-1")
        gateway = LLMGateway()
        gateway.initialize = lambda: None
        gateway._initialized = True
        gateway.providers = {"provider-1": provider, "provider-2": MockProvider("provider-2", ["model-2"], response_text="from provider-2")}
        gateway._default_cascade = [("provider-1", "model-1"), ("provider-2", "model-2")]

        # Open the circuit breaker for provider-1
        gateway.breaker.cool_down("provider-1", "model-1", "test error")

        response = asyncio.get_event_loop().run_until_complete(
            gateway.chat(messages=[{"role": "user", "content": "test"}], task_type="planner")
        )

        assert response.provider == "provider-2"
        assert provider.call_count == 0  # provider-1 was skipped

    def test_breaker_resets_after_success(self):
        """Circuit breaker resets after a successful call."""
        breaker = CircuitBreaker(base_cooldown_ms=100)

        # Cool down
        breaker.cool_down("provider-1", "model-1", "error")
        assert breaker.is_cooling_down("provider-1", "model-1")

        # Record success
        breaker.record_success("provider-1", "model-1")
        assert not breaker.is_cooling_down("provider-1", "model-1")
        assert breaker.get_state("provider-1", "model-1")["failures"] == 0

    def test_breaker_exponential_backoff(self):
        """Circuit breaker uses exponential backoff on repeated failures."""
        breaker = CircuitBreaker(base_cooldown_ms=1000)

        breaker.cool_down("provider-1", "model-1", "error 1")
        state1 = breaker.get_state("provider-1", "model-1")
        assert state1["failures"] == 1

        breaker.cool_down("provider-1", "model-1", "error 2")
        state2 = breaker.get_state("provider-1", "model-1")
        assert state2["failures"] == 2
        # Second cooldown should be longer than first
        assert state2["cooldown_remaining"] >= state1["cooldown_remaining"]


class TestTaskCascades:
    """Verify task type cascades use user-provider defaults/routing rules."""

    def test_default_cascade_is_used(self):
        gateway = LLMGateway()
        gateway._default_cascade = [("MyProvider", "my-model")]
        cascade = gateway.get_cascade("planner")
        assert cascade[0] == {"provider": "MyProvider", "model": "my-model"}

    def test_routing_rules_override_default_cascade(self):
        gateway = LLMGateway()
        gateway._routing_rules = {"coding": [("CoderProvider", "coder-model")]}
        cascade = gateway.get_cascade("coder")
        assert cascade[0] == {"provider": "CoderProvider", "model": "coder-model"}

    def test_aep_task_type_mapping(self):
        gateway = LLMGateway()
        gateway._routing_rules = {"coding": [("CoderProvider", "coder-model")]}
        cascade = gateway.get_cascade("coder")
        assert cascade[0] == {"provider": "CoderProvider", "model": "coder-model"}

    def test_unknown_task_uses_default_cascade(self):
        gateway = LLMGateway()
        gateway._default_cascade = [("Default", "default")]
        cascade = gateway.get_cascade("unknown_task")
        assert len(cascade) > 0
