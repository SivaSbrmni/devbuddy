"""Reviewer — validates quality, maintainability, security of code."""

from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.core.model_router import TaskCategory


class Reviewer(BaseAgent):
    name = "reviewer"

    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        code_changes = context.get("code_changes", "")
        architecture = context.get("architecture", "")
        review_type = context.get("review_type", "code")  # code | security | architecture

        category_map = {
            "code": TaskCategory.CODE_REVIEW,
            "security": TaskCategory.SECURITY_REVIEW,
            "architecture": TaskCategory.ARCHITECTURE_REVIEW,
        }

        result = await self.llm(
            messages=[{"role": "user", "content": f"""Perform a thorough {review_type} review.

Code changes:
{code_changes}

Architecture context:
{architecture}

Evaluate:
1. Correctness — does the code do what it should?
2. Quality — is it clean, well-structured, idiomatic?
3. Security — any vulnerabilities, injection risks, secret exposure?
4. Maintainability — is it easy to understand and modify?
5. Performance — any obvious bottlenecks?
6. Test coverage — are edge cases handled?

Output a JSON object with:
- "approved": boolean
- "issues": list of {{severity: "critical"|"major"|"minor", file, line, description, suggestion}}
- "summary": overall assessment
- "score": 1-10 quality rating
"""}],
            category=category_map.get(review_type, TaskCategory.CODE_REVIEW),
            system="You are a principal engineer performing code review. Be thorough but fair. Output valid JSON only.",
            max_tokens=4096,
        )

        return {"review": result.content, "tokens": result.input_tokens + result.output_tokens}
