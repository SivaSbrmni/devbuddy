"""Tester Agent — Phase 5.

Writes unit/integration tests, runs them, parses results, and reports
coverage delta.

Spec reference: AGENTS.md Phase 5 — Tester Agent, spec §6.1.
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

_logger = aep_logger("aep.plugins.tester")

_SYSTEM_PROMPT = """\
You are an expert software testing engineer. Given code changes and context, \
write appropriate unit and integration tests.

Your response MUST be a JSON object with these fields:
- "test_files": An array of test file objects, each with:
  - "path": file path relative to the repository root (e.g. "tests/test_feature.py")
  - "content": the complete test file content
  - "framework": testing framework used (e.g. "pytest", "jest", "vitest")
  - "test_count": number of test cases in this file
- "run_command": the shell command to run these tests (e.g. "pytest tests/test_feature.py -v")
- "coverage_targets": array of module paths these tests cover
- "summary": a one-sentence summary of what is tested

Respond with ONLY the JSON object. No markdown fences, no explanation.
"""


class TesterAgent(AgentPlugin):
    """Generates tests and reports results."""

    name: ClassVar[str] = "tester"
    feature_flag: ClassVar[str] = "agent_tester_enabled"
    model: ClassVar[str] = "gemma4:31b-cloud"
    fallback_model: ClassVar[Optional[str]] = "llama3.2"
    description: ClassVar[str] = "Writes unit/integration tests and reports coverage."

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
            user_prompt += f"\n\nCode changes to test:\n{json.dumps(input.upstream, indent=2)}"
        if input.context:
            user_prompt += f"\n\nRepository context:\n{json.dumps(input.context, indent=2)}"

        try:
            result = await llm.generate(
                prompt=f"{_SYSTEM_PROMPT}\n\n{user_prompt}",
                model=self.model,
                temperature=0.1,
                max_tokens=4096,
                tenant_id=str(input.tenant_id),
                purpose="test",
            )
        except Exception as exc:
            _logger.error("tester_llm_error", error=str(exc))
            return AgentOutput(
                success=False,
                error=f"LLM call failed: {exc}",
                duration_ms=(time.monotonic() - start) * 1000,
            )

        raw_text = result.get("text", "")
        prompt_tokens = result.get("prompt_tokens", 0)
        completion_tokens = result.get("completion_tokens", 0)

        try:
            test_result = _parse_test_json(raw_text)
        except Exception as exc:
            _logger.warning("tester_parse_error", error=str(exc), raw=raw_text[:500])
            return AgentOutput(
                success=False,
                error=f"Failed to parse test output: {exc}",
                result={"raw_response": raw_text},
                token_input=prompt_tokens,
                token_output=completion_tokens,
                duration_ms=(time.monotonic() - start) * 1000,
            )

        elapsed = (time.monotonic() - start) * 1000
        test_files = test_result.get("test_files", [])
        total_tests = sum(f.get("test_count", 0) for f in test_files)

        _logger.info(
            "tests_generated",
            execution_id=str(input.execution_id),
            test_files=len(test_files),
            total_tests=total_tests,
            run_command=test_result.get("run_command", ""),
            duration_ms=elapsed,
        )

        return AgentOutput(
            success=True,
            result=test_result,
            token_input=prompt_tokens,
            token_output=completion_tokens,
            duration_ms=elapsed,
        )


def _parse_test_json(text: str) -> dict[str, Any]:
    """Extract JSON from LLM response, handling markdown fences."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines)
    return json.loads(cleaned)


get_plugin_registry().register(TesterAgent)
