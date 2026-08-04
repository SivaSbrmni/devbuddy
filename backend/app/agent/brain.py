"""DevBuddy Brain — Devin-style planner + executor in a single continuous loop."""

from __future__ import annotations

import json
import re
import uuid
from typing import Any, Callable, Awaitable

import structlog

from app.schemas.agent_session import PlanStep, SessionPlan

log = structlog.get_logger()

EmitFn = Callable[[str, dict[str, Any]], Awaitable[None]]


def _default_plan(prompt: str, has_repo: bool) -> SessionPlan:
    """Deterministic fallback plan when LLM planning is unavailable."""
    steps = [
        PlanStep(
            id="understand",
            title="Understand the task",
            goal="Analyze requirements and repository context",
            success_criteria="Clear understanding of scope and constraints",
        ),
        PlanStep(
            id="plan",
            title="Plan implementation",
            goal="Design approach and identify files to change",
            success_criteria="Implementation plan documented",
        ),
    ]
    if has_repo:
        steps.extend([
            PlanStep(
                id="implement",
                title="Implement changes",
                goal="Write and modify code in an isolated branch",
                success_criteria="Code changes committed to feature branch",
            ),
            PlanStep(
                id="validate",
                title="Validate & test",
                goal="Run build, lint, and tests",
                success_criteria="Quality checks pass or issues documented",
            ),
            PlanStep(
                id="deliver",
                title="Deliver PR",
                goal="Open pull request with summary",
                success_criteria="PR created and linked",
            ),
        ])
    else:
        steps.append(
            PlanStep(
                id="respond",
                title="Deliver response",
                goal="Provide complete answer or generated artifacts",
                success_criteria="User receives actionable output",
            )
        )

    summary = prompt.strip()[:200]
    if len(prompt) > 200:
        summary += "…"
    return SessionPlan(summary=summary, steps=steps)


def _parse_plan_json(text: str, prompt: str, has_repo: bool) -> SessionPlan:
    """Extract structured plan from LLM response."""
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return _default_plan(prompt, has_repo)
    try:
        data = json.loads(match.group())
        steps_raw = data.get("steps") or []
        steps: list[PlanStep] = []
        for i, s in enumerate(steps_raw):
            if not isinstance(s, dict):
                continue
            steps.append(PlanStep(
                id=str(s.get("id") or f"step-{i + 1}"),
                title=str(s.get("title") or f"Step {i + 1}"),
                goal=str(s.get("goal") or ""),
                success_criteria=str(s.get("success_criteria") or ""),
            ))
        if not steps:
            return _default_plan(prompt, has_repo)
        return SessionPlan(
            version=int(data.get("version") or 1),
            summary=str(data.get("summary") or prompt[:200]),
            steps=steps,
        )
    except (json.JSONDecodeError, ValueError):
        return _default_plan(prompt, has_repo)


class DevBuddyBrain:
    """Planner–executor: one context flow, structured plan, step summaries."""

    PLAN_SYSTEM = (
        "You are a principal software engineer planning an autonomous coding session. "
        "Return ONLY valid JSON with keys: version, summary, steps. "
        "Each step: id, title, goal, success_criteria. "
        "Keep 3-6 steps. Be specific to the user's task."
    )

    async def create_plan(
        self,
        prompt: str,
        *,
        has_repo: bool,
        repo_context: str = "",
        gateway: Any | None = None,
        model: str = "",
    ) -> SessionPlan:
        if not gateway or not gateway.providers:
            return _default_plan(prompt, has_repo)

        user_content = f"Task:\n{prompt}\n"
        if repo_context:
            user_content += f"\nRepository context:\n{repo_context}\n"
        if has_repo:
            user_content += "\nThe agent will work in a GitHub repository and open a PR."
        else:
            user_content += "\nNo repository connected — provide a plan for a direct response."

        messages = [
            {"role": "system", "content": self.PLAN_SYSTEM},
            {"role": "user", "content": user_content},
        ]

        try:
            response = await gateway.chat(
                messages=messages,
                task_type="planner",
                model=model or None,
                max_tokens=2048,
                temperature=0.2,
            )
            return _parse_plan_json(response.text, prompt, has_repo)
        except Exception as e:
            log.warning("brain.plan_fallback", error=str(e))
            return _default_plan(prompt, has_repo)

    async def run_with_plan(
        self,
        session_id: uuid.UUID,
        plan: SessionPlan,
        emit: EmitFn,
        execute_fn: Callable[[PlanStep, int], Awaitable[bool]],
    ) -> None:
        """Execute plan steps sequentially via the provided executor."""
        await emit("plan_updated", {"plan": plan.model_dump()})

        for index, step in enumerate(plan.steps):
            step.status = "active"
            await emit("step_started", {
                "index": index,
                "step": step.model_dump(),
            })

            try:
                success = await execute_fn(step, index)
                step.status = "completed" if success else "failed"
                summary = f"Completed: {step.title}" if success else f"Failed: {step.title}"
                await emit("step_completed", {
                    "index": index,
                    "step": step.model_dump(),
                    "summary": summary,
                    "success": success,
                })
                if not success:
                    await emit("error", {"message": f"Step failed: {step.title}"})
                    return
            except Exception as e:
                step.status = "failed"
                await emit("step_completed", {
                    "index": index,
                    "step": step.model_dump(),
                    "summary": str(e),
                    "success": False,
                })
                await emit("error", {"message": str(e)})
                return

        await emit("session_status", {"status": "completed"})
