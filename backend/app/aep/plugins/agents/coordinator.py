"""Coordinator Agent — Phase 5.

Owns the multi-agent DAG, routes AgentMessage envelopes, manages
predecessor-output reads, and orchestrates the full multi-agent
execution pipeline.

Spec reference: AGENTS.md Phase 5 — Coordinator, spec §6.3.
"""
from __future__ import annotations

import time
from collections import defaultdict
from typing import Any, ClassVar, Optional

from app.aep.observability import aep_logger
from app.aep.plugins.base import AgentPlugin
from app.aep.plugins.registry import PluginRegistry, get_plugin_registry
from app.aep.plugins.types import (
    AgentInput,
    AgentMessage,
    AgentMessageKind,
    AgentOutput,
    ExecutionPlanStep,
)

_logger = aep_logger("aep.plugins.coordinator")


class CoordinatorAgent(AgentPlugin):
    """Orchestrates multi-agent execution from an ExecutionPlan."""

    name: ClassVar[str] = "coordinator"
    feature_flag: ClassVar[str] = "multi_agent_enabled"
    model: ClassVar[str] = "gemma4:31b-cloud"
    fallback_model: ClassVar[Optional[str]] = None
    description: ClassVar[str] = "Orchestrates multi-agent DAG execution."

    def __init__(self, *, registry: Optional[PluginRegistry] = None) -> None:
        self._registry = registry

    def _get_registry(self) -> PluginRegistry:
        if self._registry is None:
            self._registry = get_plugin_registry()
        return self._registry

    async def execute(self, input: AgentInput) -> AgentOutput:
        """Execute the coordination plan from upstream planner output."""
        start = time.monotonic()

        plan_data = input.upstream
        if not plan_data or "steps" not in plan_data:
            return AgentOutput(
                success=False,
                error="No execution plan provided in upstream data",
                duration_ms=(time.monotonic() - start) * 1000,
            )

        steps = [ExecutionPlanStep(**s) for s in plan_data["steps"]]
        results = await self._execute_dag(input, steps)

        elapsed = (time.monotonic() - start) * 1000
        succeeded = sum(1 for r in results.values() if r.success)
        failed = sum(1 for r in results.values() if not r.success)

        _logger.info(
            "coordination_complete",
            execution_id=str(input.execution_id),
            total_steps=len(steps),
            succeeded=succeeded,
            failed=failed,
            duration_ms=elapsed,
        )

        all_messages: list[AgentMessage] = []
        step_results: list[dict[str, Any]] = []
        total_tokens_in = 0
        total_tokens_out = 0

        for idx, output in sorted(results.items()):
            all_messages.extend(output.messages)
            total_tokens_in += output.token_input
            total_tokens_out += output.token_output
            step_results.append({
                "step_index": idx,
                "success": output.success,
                "error": output.error,
                "result": output.result,
                "duration_ms": output.duration_ms,
            })

        overall_success = failed == 0

        return AgentOutput(
            success=overall_success,
            result={
                "steps": step_results,
                "summary": plan_data.get("summary", ""),
                "succeeded": succeeded,
                "failed": failed,
                "total_steps": len(steps),
            },
            messages=all_messages,
            token_input=total_tokens_in,
            token_output=total_tokens_out,
            duration_ms=elapsed,
            error=f"{failed} step(s) failed" if failed > 0 else None,
        )

    async def _execute_dag(
        self,
        input: AgentInput,
        steps: list[ExecutionPlanStep],
    ) -> dict[int, AgentOutput]:
        """Execute steps respecting dependency ordering (topological)."""
        registry = self._get_registry()
        results: dict[int, AgentOutput] = {}
        step_map = {s.step_index: s for s in steps}

        # Build dependency graph
        dependents: dict[int, list[int]] = defaultdict(list)
        in_degree: dict[int, int] = {}
        for step in steps:
            in_degree[step.step_index] = len(step.depends_on)
            for dep in step.depends_on:
                dependents[dep].append(step.step_index)

        # Find ready steps (no dependencies)
        ready = [idx for idx, deg in in_degree.items() if deg == 0]

        while ready:
            # Execute ready steps (could be parallelized in future)
            current = ready.pop(0)
            step = step_map[current]

            # Build upstream context from predecessor outputs
            upstream_context: dict[str, Any] = {}
            for dep_idx in step.depends_on:
                if dep_idx in results and results[dep_idx].success:
                    upstream_context[f"step_{dep_idx}"] = results[dep_idx].result

            agent = registry.get(step.agent_name)
            if agent is None:
                _logger.warning(
                    "agent_not_available",
                    agent_name=step.agent_name,
                    step_index=current,
                )
                results[current] = AgentOutput(
                    success=False,
                    error=f"Agent '{step.agent_name}' not available",
                    duration_ms=0.0,
                )
            else:
                step_input = AgentInput(
                    tenant_id=input.tenant_id,
                    execution_id=input.execution_id,
                    step_index=current,
                    repository_id=input.repository_id,
                    branch=input.branch,
                    task_description=step.description,
                    upstream=upstream_context,
                    context=input.context,
                    metadata=input.metadata,
                )

                try:
                    output = await agent.execute(step_input)
                    results[current] = output

                    # Send inter-agent message
                    msg = AgentMessage(
                        execution_id=input.execution_id,
                        sender="coordinator",
                        recipient=step.agent_name,
                        kind=AgentMessageKind.RESPONSE,
                        payload={
                            "step_index": current,
                            "success": output.success,
                        },
                    )
                    output.messages.append(msg)
                except Exception as exc:
                    _logger.error(
                        "step_execution_error",
                        step_index=current,
                        agent=step.agent_name,
                        error=str(exc),
                    )
                    results[current] = AgentOutput(
                        success=False,
                        error=f"Step execution failed: {exc}",
                        duration_ms=0.0,
                    )

            # Update dependents
            for dep_idx in dependents.get(current, []):
                in_degree[dep_idx] -= 1
                if in_degree[dep_idx] == 0:
                    # Only add to ready if all dependencies succeeded
                    deps_ok = all(
                        results.get(d, AgentOutput(success=False, duration_ms=0)).success
                        for d in step_map[dep_idx].depends_on
                    )
                    if deps_ok:
                        ready.append(dep_idx)
                    else:
                        results[dep_idx] = AgentOutput(
                            success=False,
                            error="Skipped due to failed dependency",
                            duration_ms=0.0,
                        )

        return results


# Auto-register with the plugin registry when this module is imported.
get_plugin_registry().register(CoordinatorAgent)
