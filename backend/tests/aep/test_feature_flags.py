"""
Tests for :mod:`app.aep.feature_flags`.

These tests deliberately avoid touching the database fixture — the
flag service is required to function (with env-var fallback and
defaults) even when the DB is unavailable.
"""
from __future__ import annotations


import pytest

from app.aep.feature_flags import (
    FLAGS,
    FeatureFlagService,
    reset_feature_flag_service,
    get_feature_flag_service,
)


@pytest.fixture(autouse=True)
def _reset_service():
    reset_feature_flag_service()
    yield
    reset_feature_flag_service()


class TestFlagDefaults:
    """Every flag must default to safe values."""

    def test_master_flag_defaults_off(self):
        spec = FLAGS["autonomous_engine_enabled"]
        assert spec.default is False

    def test_every_capability_flag_defaults_off(self):
        capability_flags = [
            "llm_gateway_enabled",
            "webhook_receiver_enabled",
            "github_actions_runtime_enabled",
            "agent_planner_enabled",
            "agent_coder_enabled",
            "agent_debugger_enabled",
            "agent_tester_enabled",
            "agent_reviewer_enabled",
            "agent_security_audit_enabled",
            "agent_documentation_enabled",
            "agent_devops_enabled",
            "memory_system_enabled",
            "multi_agent_enabled",
            "autonomous_ui_enabled",
        ]
        for name in capability_flags:
            assert FLAGS[name].default is False, f"{name} must default to False"

    def test_human_approval_required_defaults_on(self):
        """Safety default — destructive ops gated on human approval."""
        assert FLAGS["human_approval_required"].default is True


class TestResolution:
    async def test_unknown_flag_returns_false(self):
        ff = FeatureFlagService()
        assert await ff.is_enabled("definitely_not_a_real_flag") is False

    async def test_capability_flag_off_when_master_off(self, monkeypatch):
        """Master flag false forces every capability flag to false."""
        monkeypatch.delenv("AEP_FLAG_AUTONOMOUS_ENGINE_ENABLED", raising=False)
        monkeypatch.setenv("AEP_FLAG_LLM_GATEWAY_ENABLED", "true")
        ff = FeatureFlagService()
        assert await ff.is_enabled("llm_gateway_enabled") is False

    async def test_capability_flag_on_when_master_on(self, monkeypatch):
        monkeypatch.setenv("AEP_FLAG_AUTONOMOUS_ENGINE_ENABLED", "true")
        monkeypatch.setenv("AEP_FLAG_LLM_GATEWAY_ENABLED", "true")
        ff = FeatureFlagService()
        assert await ff.is_enabled("llm_gateway_enabled") is True

    async def test_env_var_fallback_truthy(self, monkeypatch):
        monkeypatch.setenv("AEP_FLAG_AUTONOMOUS_ENGINE_ENABLED", "1")
        ff = FeatureFlagService()
        assert await ff.is_enabled("autonomous_engine_enabled") is True

    async def test_env_var_fallback_falsy(self, monkeypatch):
        monkeypatch.setenv("AEP_FLAG_AUTONOMOUS_ENGINE_ENABLED", "off")
        ff = FeatureFlagService()
        assert await ff.is_enabled("autonomous_engine_enabled") is False

    async def test_human_approval_independent_of_master(self, monkeypatch):
        """human_approval_required must evaluate even if master is off."""
        monkeypatch.delenv("AEP_FLAG_AUTONOMOUS_ENGINE_ENABLED", raising=False)
        ff = FeatureFlagService()
        # Default is True; master off must not force it to False.
        assert await ff.is_enabled("human_approval_required") is True


class TestCache:
    async def test_repeated_lookups_hit_cache(self, monkeypatch):
        monkeypatch.setenv("AEP_FLAG_AUTONOMOUS_ENGINE_ENABLED", "true")
        ff = FeatureFlagService()
        # First call resolves and writes the cache.
        first = await ff.is_enabled("autonomous_engine_enabled")
        # Flip env var; cache should mask the change.
        monkeypatch.setenv("AEP_FLAG_AUTONOMOUS_ENGINE_ENABLED", "false")
        second = await ff.is_enabled("autonomous_engine_enabled")
        assert first is True
        assert second is True
        ff.invalidate_cache()
        third = await ff.is_enabled("autonomous_engine_enabled")
        assert third is False


class TestSingleton:
    def test_singleton_returns_same_instance(self):
        a = get_feature_flag_service()
        b = get_feature_flag_service()
        assert a is b

    def test_reset_returns_new_instance(self):
        a = get_feature_flag_service()
        reset_feature_flag_service()
        b = get_feature_flag_service()
        assert a is not b


class TestSetValidation:
    """Writes must reject unknown flag names without touching the DB."""

    async def test_set_unknown_flag_raises(self):
        ff = FeatureFlagService()
        with pytest.raises(ValueError):
            await ff.set("not_a_real_flag", True, db=None)  # type: ignore[arg-type]
