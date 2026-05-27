"""Tests for the plugin registry."""
from __future__ import annotations

import pytest

from app.aep.feature_flags import (
    reset_feature_flag_service,
)
from app.aep.plugins import (
    AgentInput,
    AgentOutput,
    AgentPlugin,
    PluginRegistry,
    reset_plugin_registry,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_plugin_registry()
    reset_feature_flag_service()
    yield
    reset_plugin_registry()
    reset_feature_flag_service()


class _StubAgent(AgentPlugin):
    name = "stub"
    feature_flag = "agent_planner_enabled"
    model = "test:1"
    description = "Stub agent used for unit tests"

    async def execute(self, input: AgentInput) -> AgentOutput:  # pragma: no cover
        return AgentOutput(success=True)


class TestRegistrationContract:
    def test_subclass_without_required_attrs_raises(self):
        with pytest.raises(TypeError):
            class _Bad(AgentPlugin):  # noqa: D401
                async def execute(self, input: AgentInput) -> AgentOutput:
                    return AgentOutput(success=True)

    def test_register_rejects_non_subclass(self):
        registry = PluginRegistry()
        with pytest.raises(TypeError):
            registry.register(object)  # type: ignore[arg-type]


class TestActivationFlagGating:
    async def test_inactive_when_flag_off(self, monkeypatch):
        monkeypatch.delenv("AEP_FLAG_AUTONOMOUS_ENGINE_ENABLED", raising=False)
        monkeypatch.delenv("AEP_FLAG_AGENT_PLANNER_ENABLED", raising=False)
        registry = PluginRegistry()
        registry.register(_StubAgent)
        active = await registry.activate_registered()
        assert active == []
        assert registry.get("stub") is None
        # Class is still registered even though not active.
        assert registry.get_class("stub") is _StubAgent

    async def test_active_when_master_and_flag_on(self, monkeypatch):
        monkeypatch.setenv("AEP_FLAG_AUTONOMOUS_ENGINE_ENABLED", "true")
        monkeypatch.setenv("AEP_FLAG_AGENT_PLANNER_ENABLED", "true")
        registry = PluginRegistry()
        registry.register(_StubAgent)
        active = await registry.activate_registered()
        assert active == ["stub"]
        assert isinstance(registry.get("stub"), _StubAgent)

    async def test_deactivation_drops_instance(self, monkeypatch):
        monkeypatch.setenv("AEP_FLAG_AUTONOMOUS_ENGINE_ENABLED", "true")
        monkeypatch.setenv("AEP_FLAG_AGENT_PLANNER_ENABLED", "true")
        registry = PluginRegistry()
        registry.register(_StubAgent)
        await registry.activate_registered()
        assert registry.get("stub") is not None
        # Now turn the flag off and re-activate — the instance should drop.
        monkeypatch.setenv("AEP_FLAG_AGENT_PLANNER_ENABLED", "false")
        registry._ff.invalidate_cache()  # noqa: SLF001
        await registry.activate_registered()
        assert registry.get("stub") is None


class TestDiscovery:
    """Phase 0 invariant: app.aep.plugins.agents is empty."""

    async def test_discover_finds_no_agents_in_phase_0(self):
        registry = PluginRegistry()
        active = await registry.discover()
        assert active == []
        assert registry.list_active() == []
        assert registry.list_registered() == []

    async def test_discover_missing_package_returns_empty(self):
        registry = PluginRegistry()
        active = await registry.discover(package="does.not.exist.anywhere")
        assert active == []


class TestInfo:
    def test_info_reports_registered_metadata(self):
        registry = PluginRegistry()
        registry.register(_StubAgent)
        info = registry.info()
        assert len(info) == 1
        entry = info[0]
        assert entry["name"] == "stub"
        assert entry["feature_flag"] == "agent_planner_enabled"
        assert entry["model"] == "test:1"
        assert entry["active"] is False
        assert entry["description"] == "Stub agent used for unit tests"
