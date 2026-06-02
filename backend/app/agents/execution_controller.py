"""Execution Controller — monitors execution, collects artifacts, tracks status."""

from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.core.model_router import TaskCategory


class ExecutionController(BaseAgent):
    name = "execution_controller"

    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        run_logs = context.get("run_logs", "")
        run_status = context.get("run_status", "")
        artifacts = context.get("artifacts", [])

        # Use Llama for log analysis (cheap, fast)
        analysis = await self.llm(
            messages=[{"role": "user", "content": f"""Analyze this execution run.

Status: {run_status}

Logs:
{run_logs}

Artifacts collected: {len(artifacts)}

Output a JSON object with:
- "status_summary": one-line summary
- "success": boolean
- "failures": list of {{type, message, location, severity}}
- "warnings": list of strings
- "metrics": {{duration_s, tests_passed, tests_failed, coverage_pct}}
- "next_action": "proceed"|"repair"|"abort"|"human_review"
- "evidence_for_repair": relevant log excerpts if repair needed
"""}],
            category=TaskCategory.LOG_ANALYSIS,
            system="You are an execution monitor. Analyze build/test results accurately. Output valid JSON only.",
            max_tokens=4096,
        )

        return {
            "execution_analysis": analysis.content,
            "tokens": analysis.input_tokens + analysis.output_tokens,
        }
