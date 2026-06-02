"""Planner — creates milestones, builds task graphs, generates execution plans."""

from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.core.model_router import TaskCategory


class Planner(BaseAgent):
    name = "planner"

    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        specification = context.get("specification", "")
        project_memory = context.get("project_memory", "")

        # Phase 1: Llama drafts plan
        draft = await self.llm(
            messages=[{"role": "user", "content": f"""Create a phased implementation plan from this specification.

Specification:
{specification}

Project memory / context:
{project_memory}

Output a JSON object with:
- "milestones": list of {{title, description, order, estimated_tasks}}
- "task_graph": list of {{id, title, type, dependencies: list[id], milestone, description}}
- "execution_order": ordered list of task ids
- "risk_assessment": list of {{risk, mitigation, probability}}
- "estimated_effort": string summary
"""}],
            category=TaskCategory.PLANNING_DRAFT,
            system="You are a senior technical project planner. Output valid JSON only.",
            max_tokens=4096,
        )

        # Phase 2: Claude reviews and finalizes
        review = await self.llm(
            messages=[{"role": "user", "content": f"""Review and finalize this implementation plan.

Specification:
{specification}

Draft plan:
{draft.content}

Verify task ordering, dependencies, completeness. Output a corrected JSON plan in the same schema.
"""}],
            category=TaskCategory.ARCHITECTURE_REVIEW,
            system="You are a principal engineer reviewing an implementation plan. Output valid JSON only.",
            max_tokens=4096,
        )

        return {
            "plan": review.content,
            "draft_tokens": draft.input_tokens + draft.output_tokens,
            "review_tokens": review.input_tokens + review.output_tokens,
        }
