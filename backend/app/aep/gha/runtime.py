"""GHA Runtime Manager — Phase 3.

Generates GitHub Actions workflow YAML from an :class:`ExecutionPlanStep`,
dispatches workflow runs through the GitHub client, and monitors their
completion via webhook events.

Spec reference: AGENTS.md Phase 3 — GHA Runtime Manager.
"""
from __future__ import annotations

import textwrap
import uuid
from typing import Any, Optional

from app.aep.github.client import GitHubClient, get_github_client
from app.aep.observability import aep_logger
from app.aep.plugins.types import ExecutionPlanStep

_logger = aep_logger("aep.gha.runtime")


class GhaRuntimeManager:
    """Generates and dispatches GitHub Actions workflows for AEP steps."""

    def __init__(self, *, github_client: Optional[GitHubClient] = None) -> None:
        self._gh = github_client

    def _get_client(self) -> GitHubClient:
        if self._gh is None:
            self._gh = get_github_client()
        return self._gh

    def generate_workflow_yaml(
        self,
        step: ExecutionPlanStep,
        *,
        execution_id: uuid.UUID,
        repo_full_name: str,
        branch: str,
        commands: list[str],
        python_version: str = "3.12",
        node_version: str = "20",
    ) -> str:
        """Generate a workflow YAML string for the given execution step."""
        safe_name = step.agent_name.replace(" ", "-").lower()
        run_block = "\n          ".join(commands) if commands else "echo 'No commands specified'"

        yaml = textwrap.dedent(f"""\
            name: "aep-{safe_name}-{step.step_index}"
            on:
              workflow_dispatch:
                inputs:
                  execution_id:
                    description: "AEP execution ID"
                    required: true
                  step_index:
                    description: "Step index within the execution plan"
                    required: true

            permissions:
              contents: write
              pull-requests: write

            jobs:
              execute:
                runs-on: ubuntu-latest
                timeout-minutes: 30
                steps:
                  - uses: actions/checkout@v4
                    with:
                      ref: "{branch}"

                  - uses: actions/setup-python@v5
                    with:
                      python-version: "{python_version}"

                  - uses: actions/setup-node@v4
                    with:
                      node-version: "{node_version}"

                  - name: "AEP Step {step.step_index}: {step.description}"
                    env:
                      AEP_EXECUTION_ID: "${{{{ inputs.execution_id }}}}"
                      AEP_STEP_INDEX: "${{{{ inputs.step_index }}}}"
                    run: |
                      {run_block}

                  - name: Report result
                    if: always()
                    run: |
                      echo "step_result=${{{{ job.status }}}}" >> $GITHUB_OUTPUT
        """)
        return yaml

    async def dispatch_workflow(
        self,
        *,
        owner: str,
        repo: str,
        workflow_path: str,
        branch: str,
        execution_id: uuid.UUID,
        step_index: int,
    ) -> dict[str, Any]:
        """Push a workflow file and trigger it via workflow_dispatch."""
        gh = self._get_client()
        result = await gh.dispatch_workflow(
            owner,
            repo,
            workflow_path,
            branch,
            inputs={
                "execution_id": str(execution_id),
                "step_index": str(step_index),
            },
        )
        _logger.info(
            "workflow_dispatched",
            owner=owner,
            repo=repo,
            workflow=workflow_path,
            execution_id=str(execution_id),
            step_index=step_index,
        )
        return result

    async def get_run_status(
        self, owner: str, repo: str, run_id: int,
    ) -> dict[str, Any]:
        """Get the current status of a workflow run."""
        gh = self._get_client()
        return await gh.get_workflow_run(owner, repo, run_id)


_singleton: Optional[GhaRuntimeManager] = None


def get_gha_runtime() -> GhaRuntimeManager:
    global _singleton
    if _singleton is None:
        _singleton = GhaRuntimeManager()
    return _singleton
