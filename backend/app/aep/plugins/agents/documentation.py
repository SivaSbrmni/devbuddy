"""Documentation Agent — Phase 5.

Generates and updates documentation for code changes — README updates,
API docs, inline docstrings, and architecture documents.

Spec reference: AGENTS.md Phase 5 — Documentation Agent, spec §6.1.
Uses ``mistral:7b`` per spec §6.1 routing table.
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

_logger = aep_logger("aep.plugins.documentation")

_SYSTEM_PROMPT = """\
You are an expert technical writer and documentation engineer. Given code \
changes and context, produce or update relevant documentation.

Your response MUST be a JSON object with these fields:
- "doc_files": An array of documentation file objects, each with:
  - "path": file path relative to the repository root
  - "action": one of "create", "modify", "delete"
  - "content": the complete file content
  - "doc_type": one of "readme", "api", "architecture", "changelog", "inline", "guide"
- "inline_docs": An array of inline documentation objects, each with:
  - "file": source file path
  - "function_or_class": name of the function/class to document
  - "docstring": the docstring to add or update
- "changelog_entry": optional changelog entry for the changes
- "summary": a one-sentence summary of documentation changes

Respond with ONLY the JSON object. No markdown fences, no explanation.
"""


class DocumentationAgent(AgentPlugin):
    """Generates and updates project documentation."""

    name: ClassVar[str] = "documentation"
    feature_flag: ClassVar[str] = "agent_documentation_enabled"
    model: ClassVar[str] = "mistral:7b"
    fallback_model: ClassVar[Optional[str]] = "llama3.2"
    description: ClassVar[str] = "Generates and updates documentation for code changes."

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
            user_prompt += f"\n\nCode changes:\n{json.dumps(input.upstream, indent=2)}"
        if input.context:
            user_prompt += f"\n\nRepository context:\n{json.dumps(input.context, indent=2)}"

        try:
            result = await llm.generate(
                prompt=f"{_SYSTEM_PROMPT}\n\n{user_prompt}",
                model=self.model,
                temperature=0.3,
                max_tokens=4096,
                tenant_id=str(input.tenant_id),
                purpose="documentation",
            )
        except Exception as exc:
            _logger.error("documentation_llm_error", error=str(exc))
            return AgentOutput(
                success=False,
                error=f"LLM call failed: {exc}",
                duration_ms=(time.monotonic() - start) * 1000,
            )

        raw_text = result.get("text", "")
        prompt_tokens = result.get("prompt_tokens", 0)
        completion_tokens = result.get("completion_tokens", 0)

        try:
            doc_result = _parse_doc_json(raw_text)
        except Exception as exc:
            _logger.warning("documentation_parse_error", error=str(exc), raw=raw_text[:500])
            return AgentOutput(
                success=False,
                error=f"Failed to parse documentation output: {exc}",
                result={"raw_response": raw_text},
                token_input=prompt_tokens,
                token_output=completion_tokens,
                duration_ms=(time.monotonic() - start) * 1000,
            )

        elapsed = (time.monotonic() - start) * 1000
        doc_files = doc_result.get("doc_files", [])
        inline_docs = doc_result.get("inline_docs", [])

        _logger.info(
            "documentation_generated",
            execution_id=str(input.execution_id),
            doc_files_count=len(doc_files),
            inline_docs_count=len(inline_docs),
            duration_ms=elapsed,
        )

        return AgentOutput(
            success=True,
            result=doc_result,
            token_input=prompt_tokens,
            token_output=completion_tokens,
            duration_ms=elapsed,
        )


def _parse_doc_json(text: str) -> dict[str, Any]:
    """Extract JSON from LLM response, handling markdown fences."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines)
    return json.loads(cleaned)


get_plugin_registry().register(DocumentationAgent)
