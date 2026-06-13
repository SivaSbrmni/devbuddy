"""DevOps Agent — Phase 5.

Generates or modifies CI/CD config, Dockerfiles, infrastructure-as-code,
and deployment configurations.

Spec reference: AGENTS.md Phase 5 — DevOps Agent, spec §6.1.
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

_logger = aep_logger("aep.plugins.devops")

_SYSTEM_PROMPT = """\
You are an expert DevOps and infrastructure engineer. Given a task and \
repository context, generate or modify CI/CD pipelines, Dockerfiles, \
infrastructure-as-code, and deployment configurations.

Your response MUST be a JSON object with these fields:
- "files": An array of file change objects, each with:
  - "path": file path relative to the repository root
  - "action": one of "create", "modify", "delete"
  - "content": the complete file content (for create/modify) or null (for delete)
  - "file_type": one of "dockerfile", "ci_workflow", "k8s_manifest", \
    "terraform", "docker_compose", "nginx_config", "env_template", "script", "other"
- "deployment_strategy": one of "rolling", "blue_green", "canary", "recreate", null
- "environment_variables": array of objects with "name", "description", \
  "required" (boolean), "default" (optional) for any new env vars needed
- "secrets_required": array of secret names that must be configured
- "validation_commands": array of shell commands to validate the configuration
- "summary": a one-sentence summary of infrastructure changes
- "risks": array of potential risks or breaking changes

Respond with ONLY the JSON object. No markdown fences, no explanation.
"""


class DevOpsAgent(AgentPlugin):
    """Generates CI/CD, Docker, and infrastructure configurations."""

    name: ClassVar[str] = "devops"
    feature_flag: ClassVar[str] = "agent_devops_enabled"
    model: ClassVar[str] = "gemma4:31b-cloud"
    fallback_model: ClassVar[Optional[str]] = "llama3.2"
    description: ClassVar[str] = "Generates CI/CD pipelines, Dockerfiles, and infra-as-code."

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
            user_prompt += f"\n\nUpstream context:\n{json.dumps(input.upstream, indent=2)}"
        if input.context:
            user_prompt += f"\n\nRepository context:\n{json.dumps(input.context, indent=2)}"

        try:
            result = await llm.generate(
                prompt=f"{_SYSTEM_PROMPT}\n\n{user_prompt}",
                model=self.model,
                temperature=0.1,
                max_tokens=4096,
                tenant_id=str(input.tenant_id),
                purpose="devops",
            )
        except Exception as exc:
            _logger.error("devops_llm_error", error=str(exc))
            return AgentOutput(
                success=False,
                error=f"LLM call failed: {exc}",
                duration_ms=(time.monotonic() - start) * 1000,
            )

        raw_text = result.get("text", "")
        prompt_tokens = result.get("prompt_tokens", 0)
        completion_tokens = result.get("completion_tokens", 0)

        try:
            devops_result = _parse_devops_json(raw_text)
        except Exception as exc:
            _logger.warning("devops_parse_error", error=str(exc), raw=raw_text[:500])
            return AgentOutput(
                success=False,
                error=f"Failed to parse devops output: {exc}",
                result={"raw_response": raw_text},
                token_input=prompt_tokens,
                token_output=completion_tokens,
                duration_ms=(time.monotonic() - start) * 1000,
            )

        elapsed = (time.monotonic() - start) * 1000
        files = devops_result.get("files", [])
        secrets_required = devops_result.get("secrets_required", [])

        _logger.info(
            "devops_complete",
            execution_id=str(input.execution_id),
            files_count=len(files),
            secrets_required=len(secrets_required),
            deployment_strategy=devops_result.get("deployment_strategy"),
            duration_ms=elapsed,
        )

        return AgentOutput(
            success=True,
            result=devops_result,
            token_input=prompt_tokens,
            token_output=completion_tokens,
            duration_ms=elapsed,
        )


def _parse_devops_json(text: str) -> dict[str, Any]:
    """Extract JSON from LLM response, handling markdown fences."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines)
    return json.loads(cleaned)


get_plugin_registry().register(DevOpsAgent)
