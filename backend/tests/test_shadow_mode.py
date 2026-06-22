"""Tests for Priority 3 — Shadow-Mode Dry Runs."""

from __future__ import annotations

import asyncio

import pytest

from app.execution.gha_runtime import GHARuntimeManager, WorkflowRun, WorkflowInputs
from app.execution.shadow_mode import ExecutionModeGate, ShadowModeRuntime


class TestExecutionModeGate:
    """Should run shadow when task/repo/config requests it."""

    def test_task_requests_shadow(self):
        gate = ExecutionModeGate()
        assert gate.should_run_shadow({"execution_mode": "shadow"}, {}, {})

    def test_config_default_shadow(self):
        gate = ExecutionModeGate()
        assert gate.should_run_shadow({"execution_mode": "live"}, {}, {"shadow_mode_default": True})

    def test_high_risk_repo_forces_shadow(self):
        gate = ExecutionModeGate(high_risk_repos={"owner/risky"})
        assert gate.should_run_shadow({"execution_mode": "live"}, {"full_name": "owner/risky"}, {})

    def test_live_by_default(self):
        gate = ExecutionModeGate()
        assert not gate.should_run_shadow({"execution_mode": "live"}, {"full_name": "owner/safe"}, {})


class TestShadowModeRuntime:
    """Shadow validation is cheap and feature-flagged."""

    def test_validate_diff_only_returns_valid(self):
        result = ShadowModeRuntime.validate_diff_only({"files": ["a.py"]})
        assert result["valid"] is True
        assert "diff" in result


class TestGHARuntimeShadow:
    """In shadow mode, GHA runtime skips push and trigger."""

    @pytest.mark.asyncio
    async def test_trigger_workflow_returns_shadow_run(self):
        manager = GHARuntimeManager()
        # No GitHub token needed in shadow mode
        workflow = manager.generate_workflow(
            type("Plan", (), {"task_id": "t1", "steps": [], "estimated_cost": {}})()
        )
        run = await manager.trigger_workflow(
            {"owner": "o", "repo": "r"},
            workflow,
            WorkflowInputs(task_payload="", execution_id=""),
            shadow_mode=True,
        )
        assert isinstance(run, WorkflowRun)
        assert run.status == "shadow"
        assert run.id == ""
