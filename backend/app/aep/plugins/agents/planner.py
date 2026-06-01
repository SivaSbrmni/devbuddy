"""Planner Agent — Phase 3.

Takes a raw task description and produces an :class:`ExecutionPlan`
via the LLM gateway. The plan is a DAG of steps with agent assignments,
dependency edges, and token estimates.

Spec reference: AGENTS.md Phase 3 — Planner Agent, spec §6.1.
"""
from __future__ import annotations

import json
from typing import Any, ClassVar, Optional

from app.aep.llm.gateway import LlmGatewayService, get_llm_gateway_service
from app.aep.observability import aep_logger
from app.aep.plugins.base import AgentPlugin
from app.aep.plugins.registry import get_plugin_registry
from app.aep.plugins.types import (
    AgentInput,
    AgentOutput,
    ExecutionPlan,
    ExecutionPlanStep,
)

_logger = aep_logger("aep.plugins.planner")

_SYSTEM_PROMPT = """\
You are an expert software engineering project planner. Given a task description and optional repository context, produce a structured execution plan.

Your plan MUST be a JSON object with these fields:
- "summary": A one-sentence summary of the plan.
- "steps": An array of step objects, each with:
  - "step_index": integer starting from 0
  - "agent_name": one of "planner", "coder", "debugger", "tester", "reviewer", "documentation", "devops"
  - "description": what this step does
  - "depends_on": array of step_index values this step depends on (empty for root steps)
  - "estimated_tokens": rough token estimate for this step
  - "requires_github_actions": boolean — true if this step needs to run in a GHA runner

Respond with ONLY the JSON object. No markdown fences, no explanation.
"""


class PlannerAgent(AgentPlugin):
    """Decomposes a task into an execution plan."""

    name: ClassVar[str] = "planner"
    feature_flag: ClassVar[str] = "agent_planner_enabled"
    model: ClassVar[str] = "gemma4:31b-cloud"
    fallback_model: ClassVar[Optional[str]] = "llama3.2"
    description: ClassVar[str] = "Decomposes tasks into structured execution plans."

    def __init__(self, *, llm: Optional[LlmGatewayService] = None) -> None:
        self._llm = llm

    def _get_llm(self) -> LlmGatewayService:
        if self._llm is None:
            self._llm = get_llm_gateway_service()
        return self._llm

    async def execute(self, input: AgentInput) -> AgentOutput:
        import time

        start = time.monotonic()
        llm = self._get_llm()

        user_prompt = f"Task: {input.task_description}"
        if input.context:
            user_prompt += f"\n\nContext:\n{json.dumps(input.context, indent=2)}"

        try:
            result = await llm.generate(
                prompt=f"{_SYSTEM_PROMPT}\n\n{user_prompt}",
                model=self.model,
                temperature=0.1,
                max_tokens=2048,
                tenant_id=str(input.tenant_id),
                purpose="plan",
            )
        except Exception as exc:
            _logger.error("planner_llm_error", error=str(exc))
            return AgentOutput(
                success=False,
                error=f"LLM call failed: {exc}",
                duration_ms=(time.monotonic() - start) * 1000,
            )

        raw_text = result.get("text", "")
        prompt_tokens = result.get("prompt_tokens", 0)
        completion_tokens = result.get("completion_tokens", 0)

        try:
            plan_data = _parse_plan_json(raw_text)
            plan = ExecutionPlan(
                execution_id=input.execution_id,
                summary=plan_data.get("summary", ""),
                steps=[
                    ExecutionPlanStep(**s) for s in plan_data.get("steps", [])
                ],
                estimated_tokens=sum(
                    s.get("estimated_tokens", 0) for s in plan_data.get("steps", [])
                ),
                requires_github_actions=any(
                    s.get("requires_github_actions", False)
                    for s in plan_data.get("steps", [])
                ),
            )
        except Exception as exc:
            _logger.warning("planner_parse_error", error=str(exc), raw=raw_text[:500])
            return AgentOutput(
                success=False,
                error=f"Failed to parse plan: {exc}",
                result={"raw_response": raw_text},
                token_input=prompt_tokens,
                token_output=completion_tokens,
                duration_ms=(time.monotonic() - start) * 1000,
            )

        elapsed = (time.monotonic() - start) * 1000
        _logger.info(
            "plan_generated",
            execution_id=str(input.execution_id),
            steps=len(plan.steps),
            estimated_tokens=plan.estimated_tokens,
            duration_ms=elapsed,
        )

        return AgentOutput(
            success=True,
            result=plan.model_dump(mode="json"),
            token_input=prompt_tokens,
            token_output=completion_tokens,
            duration_ms=elapsed,
        )


def _parse_plan_json(text: str) -> dict[str, Any]:
    """Extract a JSON object from LLM response text."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [line for line in lines if not line.strip().startswith("```")]
        text = "\n".join(lines)
    return json.loads(text)


# Auto-register with the plugin registry when this module is imported.
get_plugin_registry().register(PlannerAgent)
