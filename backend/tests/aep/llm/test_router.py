"""Tests for :mod:`app.aep.llm.router`."""
from __future__ import annotations

import pytest

from app.aep.llm.config import reset_aep_llm_config
from app.aep.llm.router import (
    SPEC_DEFAULT_MAPPING,
    SPEC_FALLBACK_MAPPING,
    ModelRouter,
    get_model_router,
    reset_model_router,
)


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    for key in list(SPEC_DEFAULT_MAPPING):
        monkeypatch.delenv(f"AEP_MODEL_FOR_{key.upper()}", raising=False)
    monkeypatch.delenv("AEP_DEFAULT_MODEL", raising=False)
    reset_aep_llm_config()
    reset_model_router()
    yield
    reset_aep_llm_config()
    reset_model_router()


class TestSpecDefaults:
    @pytest.mark.parametrize(
        "task_type,expected",
        [
            ("plan", "gemma4:31b-cloud"),
            ("code", "gemma4:31b-cloud"),
            ("debug", "gemma4:31b-cloud"),
            ("test", "gemma4:31b-cloud"),
            ("review", "gemma4:31b-cloud"),
            ("security_audit", "gemma4:31b-cloud"),
            ("documentation", "mistral:7b"),
            ("devops", "gemma4:31b-cloud"),
            ("embedding", "nomic-embed-text"),
            ("generic", "gemma4:31b-cloud"),
        ],
    )
    def test_default_mapping_matches_spec(self, task_type, expected):
        router = ModelRouter()
        decision = router.route(task_type)
        assert decision.primary == expected
        assert decision.source == "spec_default"
        assert decision.task_type == task_type

    @pytest.mark.parametrize(
        "task_type,expected",
        [
            ("code", "deepseek-coder"),
            ("test", "qwen2.5-coder"),
            ("documentation", "mistral:7b"),
        ],
    )
    def test_fallback_table(self, task_type, expected):
        router = ModelRouter()
        decision = router.route(task_type)
        assert decision.fallback == expected


class TestOverrides:
    def test_explicit_override_wins(self):
        router = ModelRouter()
        decision = router.route("plan", override="llama3.2:8b")
        assert decision.primary == "llama3.2:8b"
        assert decision.source == "override"

    def test_env_override_wins_over_spec_default(self, monkeypatch):
        monkeypatch.setenv("AEP_MODEL_FOR_CODE", "qwen2.5-coder:32b")
        router = ModelRouter()
        decision = router.route("code")
        assert decision.primary == "qwen2.5-coder:32b"
        assert decision.source == "env"

    def test_explicit_override_wins_over_env(self, monkeypatch):
        monkeypatch.setenv("AEP_MODEL_FOR_CODE", "qwen2.5-coder:32b")
        router = ModelRouter()
        decision = router.route("code", override="phi3:medium")
        assert decision.primary == "phi3:medium"
        assert decision.source == "override"

    def test_unknown_task_type_uses_config_default(self):
        router = ModelRouter()
        decision = router.route("kabuki_summarizer")
        assert decision.primary == "gemma4:31b-cloud"
        assert decision.source == "config_default"
        assert decision.fallback is None

    def test_case_insensitive_task_type(self):
        router = ModelRouter()
        d = router.route("Code")
        assert d.task_type == "code"
        assert d.primary == "gemma4:31b-cloud"


class TestRoutingTable:
    def test_known_task_types(self):
        router = ModelRouter()
        types = router.known_task_types()
        assert "plan" in types
        assert "embedding" in types
        # No duplicates and sorted.
        assert types == sorted(set(types))

    def test_as_mapping_returns_copy(self):
        router = ModelRouter()
        snap = router.as_mapping()
        snap["plan"] = "TAMPERED"
        # Subsequent calls must not reflect the mutation.
        again = router.route("plan")
        assert again.primary == "gemma4:31b-cloud"

    def test_spec_fallback_mapping_keys_subset_of_defaults(self):
        # Every fallback target should correspond to a defined task type.
        for key in SPEC_FALLBACK_MAPPING:
            assert key in SPEC_DEFAULT_MAPPING


class TestSingleton:
    def test_get_model_router_caches(self):
        r1 = get_model_router(refresh=True)
        r2 = get_model_router()
        assert r1 is r2

    def test_refresh_returns_new_instance(self):
        r1 = get_model_router(refresh=True)
        r2 = get_model_router(refresh=True)
        assert r1 is not r2
