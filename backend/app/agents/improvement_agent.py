"""Continuous Improvement Agent — generates optimization opportunities,
tech debt tasks, improvement roadmaps."""

from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.core.model_router import TaskCategory


class ImprovementAgent(BaseAgent):
    name = "improvement_agent"

    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        project_metrics = context.get("project_metrics", {})
        recent_failures = context.get("recent_failures", [])
        codebase_summary = context.get("codebase_summary", "")
        deployment_history = context.get("deployment_history", [])

        # Llama summarizes current state (cheap)
        summary = await self.llm(
            messages=[{"role": "user", "content": f"""Summarize the current project health.

Metrics: {project_metrics}
Recent failures: {recent_failures}
Deployment history: {deployment_history}

Output a brief health assessment.
"""}],
            category=TaskCategory.SUMMARIZATION,
            system="You are a project health analyst. Be concise.",
            max_tokens=2048,
        )

        # Claude generates improvement plan
        improvements = await self.llm(
            messages=[{"role": "user", "content": f"""Generate improvement tasks for this project.

Health assessment:
{summary.content}

Codebase summary:
{codebase_summary}

Output a JSON object with:
- "improvements": list of {{title, description, category, priority, estimated_effort}}
- "tech_debt": list of {{file, issue, fix_description, priority}}
- "performance_opportunities": list of {{area, current, potential, approach}}
- "reliability_improvements": list of {{area, issue, recommendation}}
- "roadmap": ordered list of improvement phases
"""}],
            category=TaskCategory.CODE_REVIEW,
            system="You are a principal engineer planning improvements. Output valid JSON only.",
            max_tokens=4096,
        )

        return {
            "health_summary": summary.content,
            "improvement_plan": improvements.content,
            "tokens": (
                summary.input_tokens + summary.output_tokens
                + improvements.input_tokens + improvements.output_tokens
            ),
        }
