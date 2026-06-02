"""Fix Agent — evidence-based debugging following the human-like strategy.

Pipeline:
1. Observe — read the failure
2. Reproduce — confirm the issue
3. Gather Evidence — collect stack traces, logs, screenshots
4. Form Hypothesis — propose a root cause
5. Validate Hypothesis — test the hypothesis
6. Apply Fix — generate a targeted patch
7. Re-Test — verify the fix
8. Verify Resolution — confirm no regressions
"""

from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.core.model_router import TaskCategory


class FixAgent(BaseAgent):
    name = "fix_agent"

    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        failure_logs = context.get("failure_logs", "")
        stack_trace = context.get("stack_trace", "")
        source_code = context.get("source_code", "")
        previous_attempts = context.get("previous_attempts", [])
        evidence = context.get("evidence", {})

        # Phase 1: Root cause analysis (Claude — precision required)
        analysis = await self.llm(
            messages=[{"role": "user", "content": f"""Perform root cause analysis on this failure.

Failure logs:
{failure_logs}

Stack trace:
{stack_trace}

Relevant source code:
{source_code}

Evidence collected:
{evidence}

Previous fix attempts (do NOT repeat these):
{previous_attempts}

Follow the debugging strategy:
1. What is the observed failure?
2. What evidence supports the root cause?
3. What is your hypothesis?
4. What is the minimum fix?

Output a JSON object with:
- "observation": what went wrong
- "evidence_summary": key evidence points
- "hypothesis": root cause theory
- "confidence": 0.0-1.0
- "fix": {{files: list of {{path, original, patched}}, explanation}}
- "verification_steps": list of commands to verify the fix
"""}],
            category=TaskCategory.ROOT_CAUSE_ANALYSIS,
            system=(
                "You are a principal engineer debugging a production failure. "
                "Never guess — use evidence. Never repeat failed fixes. Output valid JSON only."
            ),
            max_tokens=8192,
        )

        return {
            "analysis": analysis.content,
            "tokens": analysis.input_tokens + analysis.output_tokens,
        }
