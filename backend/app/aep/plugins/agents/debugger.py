"""Debugger Agent — Phase 5.

Reads test logs and CI output, traces root cause, applies fix patches,
and iterates up to a configurable retry count.

Spec reference: AGENTS.md Phase 5 — Debugger Agent, spec §6.1.
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

_logger = aep_logger("aep.plugins.debugger")

_SYSTEM_PROMPT = """\
You are an expert software debugger. Given test failure logs, CI output, or \
error traces, identify the root cause and produce a fix.

Your response MUST be a JSON object with these fields:
- "root_cause": A clear one-paragraph explanation of the root cause.
- "fix_strategy": One of "patch", "refactor", "config_change", "dependency_update".
- "patches": An array of patch objects, each with:
  - "path": file path relative to the repository root
  - "action": one of "modify", "create", "delete"
  - "content": the complete file content (for create/modify) or null (for delete)
  - "description": what this patch does
- "confidence": float 0.0–1.0 indicating confidence in the fix
- "retry_suggested": boolean — true if you recommend running the test suite again \
  after applying patches

Respond with ONLY the JSON object. No markdown fences, no explanation.
"""

MAX_RETRY_COUNT = 3


class DebuggerAgent(AgentPlugin):
    """Traces root cause from logs and applies fix patches."""

    name: ClassVar[str] = "debugger"
    feature_flag: ClassVar[str] = "agent_debugger_enabled"
    model: ClassVar[str] = "gemma4:31b-cloud"
    fallback_model: ClassVar[Optional[str]] = "llama3.2"
    description: ClassVar[str] = "Diagnoses failures and produces fix patches."

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
            user_prompt += f"\n\nError logs / CI output:\n{json.dumps(input.upstream, indent=2)}"
        if input.context:
            user_prompt += f"\n\nRepository context:\n{json.dumps(input.context, indent=2)}"

        retry_count = input.metadata.get("retry_count", 0)
        if retry_count > 0:
            user_prompt += f"\n\nThis is retry attempt {retry_count}/{MAX_RETRY_COUNT}."
            if input.metadata.get("previous_fix"):
                user_prompt += (
                    f"\nPrevious fix attempt:\n"
                    f"{json.dumps(input.metadata['previous_fix'], indent=2)}"
                )

        try:
            result = await llm.generate(
                prompt=f"{_SYSTEM_PROMPT}\n\n{user_prompt}",
                model=self.model,
                temperature=0.2,
                max_tokens=4096,
                tenant_id=str(input.tenant_id),
                purpose="debug",
            )
        except Exception as exc:
            _logger.error("debugger_llm_error", error=str(exc))
            return AgentOutput(
                success=False,
                error=f"LLM call failed: {exc}",
                duration_ms=(time.monotonic() - start) * 1000,
            )

        raw_text = result.get("text", "")
        prompt_tokens = result.get("prompt_tokens", 0)
        completion_tokens = result.get("completion_tokens", 0)

        try:
            debug_result = _parse_debug_json(raw_text)
        except Exception as exc:
            _logger.warning("debugger_parse_error", error=str(exc), raw=raw_text[:500])
            return AgentOutput(
                success=False,
                error=f"Failed to parse debug output: {exc}",
                result={"raw_response": raw_text},
                token_input=prompt_tokens,
                token_output=completion_tokens,
                duration_ms=(time.monotonic() - start) * 1000,
            )

        elapsed = (time.monotonic() - start) * 1000
        patches = debug_result.get("patches", [])
        confidence = debug_result.get("confidence", 0.0)

        _logger.info(
            "debug_complete",
            execution_id=str(input.execution_id),
            root_cause=debug_result.get("root_cause", "")[:200],
            patches_count=len(patches),
            confidence=confidence,
            retry_suggested=debug_result.get("retry_suggested", False),
            duration_ms=elapsed,
        )

        follow_up: list[str] = []
        if debug_result.get("retry_suggested") and retry_count < MAX_RETRY_COUNT:
            follow_up.append("tester")

        return AgentOutput(
            success=True,
            result=debug_result,
            token_input=prompt_tokens,
            token_output=completion_tokens,
            duration_ms=elapsed,
            follow_up=follow_up,
        )


def _parse_debug_json(text: str) -> dict[str, Any]:
    """Extract JSON from LLM response, handling markdown fences."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines)
    return json.loads(cleaned)


get_plugin_registry().register(DebuggerAgent)
