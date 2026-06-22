"""Tests for UserModelRouter cost estimation and provider readiness."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

from app.llm.providers.base import NormalizedResponse
from app.llm.providers.user_provider import UserProviderAdapter
from app.llm.user_model_router import UserModelRouter
from app.models.llm_provider import UserLLMProvider


def _normalized_response(text: str, provider: str, input_tokens: int, output_tokens: int) -> NormalizedResponse:
    return NormalizedResponse(
        text=text,
        provider=provider,
        model="gpt-4",
        latency_ms=100,
        usage={"input_tokens": input_tokens, "output_tokens": output_tokens},
    )


def _make_adapter(cost_input: float = 0.0, cost_output: float = 0.0) -> UserProviderAdapter:
    record = UserLLMProvider(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        name="Test Provider",
        provider_type="openai-compatible",
        base_url="https://example.com/v1",
        api_key_encrypted="",
        headers={},
        default_model="gpt-4",
        available_models=["gpt-4"],
        cost_per_1k_input=cost_input,
        cost_per_1k_output=cost_output,
    )
    adapter = UserProviderAdapter(record)
    adapter._api_key = "test-key"
    return adapter


def test_has_providers_false_before_init():
    router = UserModelRouter(user_id=uuid.uuid4(), db=None)
    assert router.has_providers is False


def test_estimate_cost_uses_provider_rates():
    router = UserModelRouter(user_id=uuid.uuid4(), db=None)
    mock_gateway = MagicMock()
    adapter = _make_adapter(cost_input=0.003, cost_output=0.015)
    mock_gateway.providers = {"test-provider": adapter}
    router._gateway = mock_gateway

    response = _normalized_response("hello", "test-provider", 1000, 500)
    cost = router._estimate_cost(response)

    assert cost == (1000 * 0.003 / 1000) + (500 * 0.015 / 1000)


def test_estimate_cost_returns_zero_for_unknown_provider():
    router = UserModelRouter(user_id=uuid.uuid4(), db=None)
    mock_gateway = MagicMock()
    mock_gateway.providers = {}
    router._gateway = mock_gateway

    response = _normalized_response("hello", "unknown", 1000, 500)
    cost = router._estimate_cost(response)

    assert cost == 0.0


def test_estimate_cost_returns_zero_for_non_user_provider():
    router = UserModelRouter(user_id=uuid.uuid4(), db=None)
    mock_gateway = MagicMock()
    mock_gateway.providers = {"test-provider": MagicMock()}  # not a UserProviderAdapter
    router._gateway = mock_gateway

    response = _normalized_response("hello", "test-provider", 1000, 500)
    cost = router._estimate_cost(response)

    assert cost == 0.0
