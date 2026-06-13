"""Security Audit Agent — Phase 5.

Scans for vulnerabilities, secret leakage, injection risks, and
dependency issues in generated code.

Spec reference: AGENTS.md Phase 5 — Security Audit Agent, spec §6.1.
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

_logger = aep_logger("aep.plugins.security_audit")

_SYSTEM_PROMPT = """\
You are an expert application security engineer. Given code changes and \
repository context, perform a thorough security audit.

Your response MUST be a JSON object with these fields:
- "risk_level": one of "critical", "high", "medium", "low", "none"
- "summary": a one-paragraph summary of the security posture
- "vulnerabilities": An array of vulnerability objects, each with:
  - "severity": one of "critical", "high", "medium", "low"
  - "category": one of "injection", "auth", "crypto", "secrets", "xss", \
    "ssrf", "path_traversal", "dependency", "config", "other"
  - "file": file path where the vulnerability is found
  - "line": approximate line number (0 if not applicable)
  - "title": short vulnerability title (CWE reference if applicable)
  - "description": detailed explanation of the vulnerability
  - "remediation": specific fix recommendation
  - "cwe_id": CWE identifier if applicable (e.g. "CWE-89")
- "secrets_detected": array of objects with "file", "line", "pattern" for any \
  potential secrets/credentials found in code
- "dependency_issues": array of objects with "package", "version", "advisory" \
  for known vulnerable dependencies
- "recommendations": array of general security improvement suggestions
- "passed_checks": array of security checks that passed (for positive reporting)

Respond with ONLY the JSON object. No markdown fences, no explanation.
"""


class SecurityAuditAgent(AgentPlugin):
    """Scans for security vulnerabilities and secrets leakage."""

    name: ClassVar[str] = "security_audit"
    feature_flag: ClassVar[str] = "agent_security_audit_enabled"
    model: ClassVar[str] = "gemma4:31b-cloud"
    fallback_model: ClassVar[Optional[str]] = "llama3.2"
    description: ClassVar[str] = "Scans for vulnerabilities, secrets, and dependency issues."

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
            user_prompt += f"\n\nCode to audit:\n{json.dumps(input.upstream, indent=2)}"
        if input.context:
            user_prompt += f"\n\nRepository context:\n{json.dumps(input.context, indent=2)}"

        try:
            result = await llm.generate(
                prompt=f"{_SYSTEM_PROMPT}\n\n{user_prompt}",
                model=self.model,
                temperature=0.1,
                max_tokens=4096,
                tenant_id=str(input.tenant_id),
                purpose="security",
            )
        except Exception as exc:
            _logger.error("security_audit_llm_error", error=str(exc))
            return AgentOutput(
                success=False,
                error=f"LLM call failed: {exc}",
                duration_ms=(time.monotonic() - start) * 1000,
            )

        raw_text = result.get("text", "")
        prompt_tokens = result.get("prompt_tokens", 0)
        completion_tokens = result.get("completion_tokens", 0)

        try:
            audit_result = _parse_audit_json(raw_text)
        except Exception as exc:
            _logger.warning(
                "security_audit_parse_error", error=str(exc), raw=raw_text[:500]
            )
            return AgentOutput(
                success=False,
                error=f"Failed to parse audit output: {exc}",
                result={"raw_response": raw_text},
                token_input=prompt_tokens,
                token_output=completion_tokens,
                duration_ms=(time.monotonic() - start) * 1000,
            )

        elapsed = (time.monotonic() - start) * 1000
        vulns = audit_result.get("vulnerabilities", [])
        secrets_found = audit_result.get("secrets_detected", [])

        _logger.info(
            "security_audit_complete",
            execution_id=str(input.execution_id),
            risk_level=audit_result.get("risk_level", "unknown"),
            vulnerabilities_count=len(vulns),
            secrets_detected=len(secrets_found),
            duration_ms=elapsed,
        )

        # If critical vulnerabilities found, suggest blocking the PR
        follow_up: list[str] = []
        if audit_result.get("risk_level") in ("critical", "high"):
            follow_up.append("coder")

        return AgentOutput(
            success=True,
            result=audit_result,
            token_input=prompt_tokens,
            token_output=completion_tokens,
            duration_ms=elapsed,
            follow_up=follow_up,
        )


def _parse_audit_json(text: str) -> dict[str, Any]:
    """Extract JSON from LLM response, handling markdown fences."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines)
    return json.loads(cleaned)


get_plugin_registry().register(SecurityAuditAgent)
