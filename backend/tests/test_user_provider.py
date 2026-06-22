"""Tests for UserProviderAdapter configuration detection."""

from __future__ import annotations

import uuid

from app.llm.providers.user_provider import UserProviderAdapter
from app.models.llm_provider import UserLLMProvider


def _make_record(
    provider_type: str = "openai-compatible",
    base_url: str = "https://example.com/v1",
    api_key: str = "",
    headers: dict | None = None,
) -> UserLLMProvider:
    return UserLLMProvider(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        name="Test Provider",
        provider_type=provider_type,
        base_url=base_url,
        api_key_encrypted="",
        headers=headers or {},
        default_model="gpt-4",
        available_models=["gpt-4"],
    )


def test_is_configured_with_api_key():
    record = _make_record(api_key="")
    adapter = UserProviderAdapter(record)
    adapter._api_key = "secret-key"
    assert adapter.is_configured() is True


def test_is_configured_without_api_key():
    record = _make_record(api_key="")
    adapter = UserProviderAdapter(record)
    adapter._api_key = ""
    assert adapter.is_configured() is False


def test_is_configured_with_auth_header():
    record = _make_record(
        api_key="",
        headers={"api-key": "some-key"},
    )
    adapter = UserProviderAdapter(record)
    adapter._api_key = ""
    assert adapter.is_configured() is True


def test_is_configured_local_ollama_no_key():
    record = _make_record(
        provider_type="ollama",
        base_url="http://localhost:11434",
        api_key="",
    )
    adapter = UserProviderAdapter(record)
    adapter._api_key = ""
    assert adapter.is_configured() is True


def test_is_configured_remote_ollama_no_key():
    record = _make_record(
        provider_type="ollama",
        base_url="https://ollama.com",
        api_key="",
    )
    adapter = UserProviderAdapter(record)
    adapter._api_key = ""
    assert adapter.is_configured() is False
