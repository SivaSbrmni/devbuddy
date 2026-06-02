"""Requirement Analyzer — understands requirements, resolves ambiguity,
produces structured specifications."""

from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.core.model_router import TaskCategory


class RequirementAnalyzer(BaseAgent):
    name = "requirement_analyzer"

    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        raw_requirements = context.get("requirements", "")
        project_context = context.get("project_context", "")

        # Phase 1: Llama drafts the structured breakdown
        draft = await self.llm(
            messages=[{"role": "user", "content": f"""Analyze these software requirements and produce a structured specification.

Requirements:
{raw_requirements}

Project context:
{project_context}

Output a JSON object with:
- "summary": one-paragraph plain-English summary
- "functional_requirements": list of {{id, description, priority, acceptance_criteria}}
- "non_functional_requirements": list of {{id, description, category}}
- "ambiguities": list of {{id, description, suggested_resolution}}
- "assumptions": list of strings
- "dependencies": list of external dependencies
"""}],
            category=TaskCategory.REQUIREMENT_ANALYSIS,
            system="You are a senior requirements analyst. Output valid JSON only.",
            max_tokens=4096,
        )

        # Phase 2: Claude reviews the specification
        review = await self.llm(
            messages=[{"role": "user", "content": f"""Review this requirements specification for completeness, correctness, and gaps.

Original requirements:
{raw_requirements}

Draft specification:
{draft.content}

Provide a corrected JSON specification in the same schema, fixing any issues.
"""}],
            category=TaskCategory.REQUIREMENTS_REVIEW,
            system="You are a principal engineer reviewing requirements. Output valid JSON only.",
            max_tokens=4096,
        )

        return {
            "specification": review.content,
            "draft_tokens": draft.input_tokens + draft.output_tokens,
            "review_tokens": review.input_tokens + review.output_tokens,
        }
