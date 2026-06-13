"""Reviewer Agent — Phase 5.

Reviews generated diffs, comments on PRs, and produces a
severity-ranked issue list.

Spec reference: AGENTS.md Phase 5 — Reviewer Agent, spec §6.1.
"""
from __future__ import annotations

import json
import time
from typing import Any, ClassVar, Optional

from app.aep.llm.gateway import LlmGatewayService, get_llm_gateway_service
from app.aep.observability import aep_logger
from app.aep.plugins.base import AgentPlugin
from app.aep.plugins.registry import get_plugin_registry
from app.aep.plugins.types import AgentInput, AgentOutput

_logger = aep_logger("aep.plugins.reviewer")

_SYSTEM_PROMPT = """\
You are an expert code reviewer. Given code diffs and context, produce a \
thorough review with actionable feedback.

Your response MUST be a JSON object with these fields:
- "verdict": one of "approve", "request_changes", "comment"
- "summary": a one-paragraph summary of the review
- "issues": An array of issue objects, each with:
  - "severity": one of "critical", "major", "minor", "suggestion"
  - "file": file path where the issue is found
  - "line": approximate line number (0 if not applicable)
  - "title": short issue title
  - "description": detailed explanation of the issue
  - "suggestion": suggested fix (code or description)
- "strengths": array of strings noting positive aspects of the code
- "overall_quality": float 0.0–1.0 rating of overall code quality

Respond with ONLY the JSON object. No markdown fences, no explanation.
"""


class ReviewerAgent(AgentPlugin):
    """Reviews code diffs and produces severity-ranked feedback."""

    name: ClassVar[str] = "reviewer"
    feature_flag: ClassVar[str] = "agent_reviewer_enabled"
    model: ClassVar[str] = "gemma4:31b-cloud"
    fallback_model: ClassVar[Optional[str]] = "llama3.2"
    description: ClassVar[str] = "Reviews diffs and produces severity-ranked issue lists."

    def __init__(self, *, llm: Optional[LlmGatewayService] = None) -> None:
        self._llm = llm

    def _get_llm(self) -> LlmGatewayService:
        if self._llm is None:
            self._llm = get_llm_gateway_service()
        return self._llm

    async def execute(self, input: AgentInput) -> AgentOutput:
        start = time.monotonic()
        llm = self._get_llm()

        user_prompt = f"Task: {input.task_description}"
        if input.upstream:
            user_prompt += f"\n\nCode diffs to review:\n{json.dumps(input.upstream, indent=2)}"
        if input.context:
            user_prompt += f"\n\nRepository context:\n{json.dumps(input.context, indent=2)}"

        try:
            result = await llm.generate(
                prompt=f"{_SYSTEM_PROMPT}\n\n{user_prompt}",
                model=self.model,
                temperature=0.1,
                max_tokens=4096,
                tenant_id=str(input.tenant_id),
                purpose="review",
            )
        except Exception as exc:
            _logger.error("reviewer_llm_error", error=str(exc))
            return AgentOutput(
                success=False,
                error=f"LLM call failed: {exc}",
                duration_ms=(time.monotonic() - start) * 1000,
            )

        raw_text = result.get("text", "")
        prompt_tokens = result.get("prompt_tokens", 0)
        completion_tokens = result.get("completion_tokens", 0)

        try:
            review_result = _parse_review_json(raw_text)
        except Exception as exc:
            _logger.warning("reviewer_parse_error", error=str(exc), raw=raw_text[:500])
            return AgentOutput(
                success=False,
                error=f"Failed to parse review output: {exc}",
                result={"raw_response": raw_text},
                token_input=prompt_tokens,
                token_output=completion_tokens,
                duration_ms=(time.monotonic() - start) * 1000,
            )

        elapsed = (time.monotonic() - start) * 1000
        issues = review_result.get("issues", [])
        critical_count = sum(1 for i in issues if i.get("severity") == "critical")

        _logger.info(
            "review_complete",
            execution_id=str(input.execution_id),
            verdict=review_result.get("verdict", ""),
            issues_count=len(issues),
            critical_count=critical_count,
            overall_quality=review_result.get("overall_quality", 0.0),
            duration_ms=elapsed,
        )

        follow_up: list[str] = []
        if review_result.get("verdict") == "request_changes":
            follow_up.append("coder")

        return AgentOutput(
            success=True,
            result=review_result,
            token_input=prompt_tokens,
            token_output=completion_tokens,
            duration_ms=elapsed,
            follow_up=follow_up,
        )


def _parse_review_json(text: str) -> dict[str, Any]:
    """Extract JSON from LLM response, handling markdown fences."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines)
    return json.loads(cleaned)


get_plugin_registry().register(ReviewerAgent)
