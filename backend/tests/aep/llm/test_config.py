"""Tests for :mod:`app.aep.llm.config`."""
from __future__ import annotations

import pytest

from app.aep.llm.config import get_aep_llm_config, reset_aep_llm_config


@pytest.fixture(autouse=True)
def _reset():
    reset_aep_llm_config()
    yield
    reset_aep_llm_config()


class TestAepLlmConfigDefaults:
    def test_default_model_matches_spec(self, monkeypatch):
        for var in (
            "AEP_DEFAULT_MODEL",
            "AEP_EMBEDDING_MODEL",
            "AEP_OLLAMA_BASE_URL",
            "OLLAMA_CLOUD_API_KEY",
            "AEP_OLLAMA_API_KEY",
        ):
            monkeypatch.delenv(var, raising=False)
        cfg = get_aep_llm_config(refresh=True)
        assert cfg.default_model == "gemma4:31b-cloud"
        assert cfg.embedding_model == "nomic-embed-text"
        assert cfg.is_cloud is False
        # base_url falls back to the core setting; just assert it's set.
        assert cfg.base_url
        assert not cfg.base_url.endswith("/")

    def test_auth_headers_no_key(self, monkeypatch):
        monkeypatch.delenv("OLLAMA_CLOUD_API_KEY", raising=False)
        monkeypatch.delenv("AEP_OLLAMA_API_KEY", raising=False)
        cfg = get_aep_llm_config(refresh=True)
        headers = cfg.auth_headers()
        assert "Authorization" not in headers
        assert headers["Accept"] == "application/json"
        assert headers["User-Agent"].startswith("devbuddy-aep")


class TestAepLlmConfigOverrides:
    def test_env_overrides(self, monkeypatch):
        monkeypatch.setenv("AEP_OLLAMA_BASE_URL", "https://ollama.devbuddy.org/")
        monkeypatch.setenv("OLLAMA_CLOUD_API_KEY", "sk-fake-key")
        monkeypatch.setenv("AEP_DEFAULT_MODEL", "llama3.2:8b")
        monkeypatch.setenv("AEP_EMBEDDING_MODEL", "mxbai-embed-large")
        monkeypatch.setenv("AEP_OLLAMA_REQUEST_TIMEOUT", "75")
        monkeypatch.setenv("AEP_OLLAMA_MAX_RETRIES", "5")

        cfg = get_aep_llm_config(refresh=True)
        assert cfg.base_url == "https://ollama.devbuddy.org"
        assert cfg.api_key == "sk-fake-key"
        assert cfg.is_cloud is True
        assert cfg.default_model == "llama3.2:8b"
        assert cfg.embedding_model == "mxbai-embed-large"
        assert cfg.request_timeout_seconds == 75.0
        assert cfg.max_retries == 5

        headers = cfg.auth_headers()
        assert headers["Authorization"] == "Bearer sk-fake-key"

    def test_alternate_api_key_env_var(self, monkeypatch):
        monkeypatch.delenv("OLLAMA_CLOUD_API_KEY", raising=False)
        monkeypatch.setenv("AEP_OLLAMA_API_KEY", "fallback-key")
        cfg = get_aep_llm_config(refresh=True)
        assert cfg.api_key == "fallback-key"
        assert cfg.is_cloud is True

    def test_blank_api_key_is_ignored(self, monkeypatch):
        monkeypatch.setenv("OLLAMA_CLOUD_API_KEY", "   ")
        cfg = get_aep_llm_config(refresh=True)
        assert cfg.api_key is None
        assert cfg.is_cloud is False

    def test_singleton_cached_until_refresh(self, monkeypatch):
        monkeypatch.delenv("OLLAMA_CLOUD_API_KEY", raising=False)
        first = get_aep_llm_config(refresh=True)
        monkeypatch.setenv("OLLAMA_CLOUD_API_KEY", "new-key")
        # No refresh ⇒ cached instance returned.
        second = get_aep_llm_config()
        assert second is first
        third = get_aep_llm_config(refresh=True)
        assert third is not first
        assert third.api_key == "new-key"
