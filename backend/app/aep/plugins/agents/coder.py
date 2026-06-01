"""Coder Agent — Phase 3.

Reads the execution plan, generates code (diffs / new files), and
opens a pull request via the GitHub client.

Spec reference: AGENTS.md Phase 3 — Coding Agent, spec §6.1.
"""
from __future__ import annotations

import base64
import json
import time
from typing import Any, ClassVar, Optional

from app.aep.github.client import GitHubClient, get_github_client
from app.aep.llm.gateway import LlmGatewayService, get_llm_gateway_service
from app.aep.observability import aep_logger
from app.aep.plugins.base import AgentPlugin
from app.aep.plugins.registry import get_plugin_registry
from app.aep.plugins.types import AgentInput, AgentOutput

_logger = aep_logger("aep.plugins.coder")

_SYSTEM_PROMPT = """\
You are an expert software engineer. Given a task description and execution plan step, generate the required code changes.

Your response MUST be a JSON object with these fields:
- "files": An array of file change objects, each with:
  - "path": file path relative to the repository root
  - "action": one of "create", "modify", "delete"
  - "content": the complete file content (for create/modify) or null (for delete)
- "commit_message": a conventional commit message describing the changes
- "summary": a one-sentence summary of what was done

Respond with ONLY the JSON object. No markdown fences, no explanation.
"""


class CoderAgent(AgentPlugin):
    """Generates code from a plan step and pushes changes."""

    name: ClassVar[str] = "coder"
    feature_flag: ClassVar[str] = "agent_coder_enabled"
    model: ClassVar[str] = "gemma4:31b-cloud"
    fallback_model: ClassVar[Optional[str]] = "deepseek-coder"
    description: ClassVar[str] = "Generates code changes and opens pull requests."

    def __init__(
        self,
        *,
        llm: Optional[LlmGatewayService] = None,
        github: Optional[GitHubClient] = None,
    ) -> None:
        self._llm = llm
        self._gh = github

    def _get_llm(self) -> LlmGatewayService:
        if self._llm is None:
            self._llm = get_llm_gateway_service()
        return self._llm

    def _get_github(self) -> GitHubClient:
        if self._gh is None:
            self._gh = get_github_client()
        return self._gh

    async def execute(self, input: AgentInput) -> AgentOutput:
        start = time.monotonic()
        llm = self._get_llm()

        user_prompt = f"Task: {input.task_description}"
        if input.upstream:
            user_prompt += f"\n\nPlan context:\n{json.dumps(input.upstream, indent=2)}"
        if input.context:
            user_prompt += f"\n\nRepository context:\n{json.dumps(input.context, indent=2)}"

        try:
            result = await llm.generate(
                prompt=f"{_SYSTEM_PROMPT}\n\n{user_prompt}",
                model=self.model,
                temperature=0.1,
                max_tokens=4096,
                tenant_id=str(input.tenant_id),
                purpose="code",
            )
        except Exception as exc:
            _logger.error("coder_llm_error", error=str(exc))
            return AgentOutput(
                success=False,
                error=f"LLM call failed: {exc}",
                duration_ms=(time.monotonic() - start) * 1000,
            )

        raw_text = result.get("text", "")
        prompt_tokens = result.get("prompt_tokens", 0)
        completion_tokens = result.get("completion_tokens", 0)

        try:
            code_result = _parse_code_json(raw_text)
        except Exception as exc:
            _logger.warning("coder_parse_error", error=str(exc), raw=raw_text[:500])
            return AgentOutput(
                success=False,
                error=f"Failed to parse code output: {exc}",
                result={"raw_response": raw_text},
                token_input=prompt_tokens,
                token_output=completion_tokens,
                duration_ms=(time.monotonic() - start) * 1000,
            )

        files = code_result.get("files", [])
        commit_message = code_result.get("commit_message", "chore: aep code changes")
        summary = code_result.get("summary", "")

        elapsed = (time.monotonic() - start) * 1000
        _logger.info(
            "code_generated",
            execution_id=str(input.execution_id),
            files_count=len(files),
            commit_message=commit_message,
            duration_ms=elapsed,
        )

        return AgentOutput(
            success=True,
            result={
                "files": files,
                "commit_message": commit_message,
                "summary": summary,
            },
            token_input=prompt_tokens,
            token_output=completion_tokens,
            duration_ms=elapsed,
        )

    async def push_changes(
        self,
        *,
        owner: str,
        repo: str,
        branch: str,
        files: list[dict[str, Any]],
        commit_message: str,
    ) -> dict[str, Any]:
        """Push generated file changes to a branch via the GitHub API."""
        gh = self._get_github()
        results: list[dict[str, Any]] = []

        for file_change in files:
            path = file_change["path"]
            action = file_change.get("action", "create")
            content = file_change.get("content", "")

            if action == "delete":
                _logger.info("coder_skip_delete", path=path)
                continue

            content_b64 = base64.b64encode(content.encode()).decode()

            existing_sha: Optional[str] = None
            if action == "modify":
                try:
                    existing = await gh.read_file(owner, repo, path, ref=branch)
                    existing_sha = existing.get("sha")
                except Exception:
                    pass

            await gh.write_file(
                owner, repo, path, content_b64, commit_message, branch,
                sha=existing_sha,
            )
            results.append({"path": path, "action": action, "status": "pushed"})

        return {"pushed_files": results}

    async def open_pr(
        self,
        *,
        owner: str,
        repo: str,
        head: str,
        base: str,
        title: str,
        body: str = "",
    ) -> dict[str, Any]:
        """Open a pull request with the pushed changes."""
        gh = self._get_github()
        return await gh.open_pull_request(
            owner, repo,
            title=title, head=head, base=base, body=body,
        )


def _parse_code_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [line for line in lines if not line.strip().startswith("```")]
        text = "\n".join(lines)
    return json.loads(text)


# Auto-register with the plugin registry when this module is imported.
get_plugin_registry().register(CoderAgent)
