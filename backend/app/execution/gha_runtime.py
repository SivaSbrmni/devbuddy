"""GitHub Actions Runtime Manager — spec Part 5.

Formalizes the GHA execution lifecycle:
  Planner builds DAG → Workflow YAML generated → workflow_dispatch triggers
  ephemeral runner → checkout → context hydration → agent steps →
  artifacts uploaded → results posted back → runner terminates.

No persistent runner state; all persistence is external.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import AsyncIterator, Optional

import structlog

log = structlog.get_logger()


@dataclass
class ExecutionPlan:
    """Execution DAG built by the Planner agent."""
    task_id: str
    steps: list[dict] = field(default_factory=list)
    agent_assignments: dict[str, str] = field(default_factory=dict)  # step_id -> agent_name
    estimated_cost: dict = field(default_factory=dict)
    feature_branch: str = ""


@dataclass
class WorkflowYAML:
    """Generated GitHub Actions workflow YAML."""
    content: str
    filename: str
    task_id: str


@dataclass
class WorkflowInputs:
    """Inputs for a workflow dispatch."""
    task_payload: str
    execution_id: str
    extra: dict = field(default_factory=dict)


@dataclass
class WorkflowRun:
    """A triggered workflow run."""
    id: str
    status: str = "queued"
    html_url: str = ""


@dataclass
class WorkflowResult:
    """Result of a completed workflow run."""
    run_id: str
    status: str
    conclusion: Optional[str] = None
    artifacts: list[dict] = field(default_factory=list)
    logs: str = ""
    duration_seconds: int = 0


@dataclass
class ArtifactBundle:
    """Downloaded artifacts from a workflow run."""
    artifacts: list[dict] = field(default_factory=list)


class GHARuntimeManager:
    """Manages GitHub Actions workflow lifecycle (spec Part 5).

    Generates workflow YAML from execution plans, triggers workflows,
    monitors their progress, and retrieves results.
    """

    WORKFLOW_TEMPLATE = """name: "aep-task-{task_id}"
on:
  workflow_dispatch:
    inputs:
      task_payload:
        description: "Compressed task payload"
        required: true
        type: string
      execution_id:
        description: "AEP execution ID"
        required: true
        type: string
env:
  AEP_PLATFORM_URL: ${{{{ secrets.AEP_PLATFORM_URL }}}}
  AEP_EXECUTION_TOKEN: ${{{{ secrets.AEP_EXECUTION_TOKEN }}}}
  AEP_EXECUTION_ID: ${{{{ github.event.inputs.execution_id }}}}
jobs:
  aep-execute:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4
        with:
          token: ${{{{ secrets.AEP_GITHUB_TOKEN }}}}
          fetch-depth: 0
      - name: Hydrate Task Context
        run: |
          curl -fsSL "$AEP_PLATFORM_URL/api/v1/executions/$AEP_EXECUTION_ID/context" \\
            -H "Authorization: Bearer $AEP_EXECUTION_TOKEN" -o .aep_context.json
      - name: Execute Agent Steps
        run: |
          {agent_steps}
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: "aep-results-${{ github.run_id }}"
          path: .aep_output/
          retention-days: 7
      - name: Report Results
        if: always()
        run: |
          curl -X POST "$AEP_PLATFORM_URL/api/v1/executions/$AEP_EXECUTION_ID/complete" \\
            -H "Authorization: Bearer $AEP_EXECUTION_TOKEN" \\
            -H "Content-Type: application/json" \\
            -d @.aep_output/result.json
"""

    def __init__(self) -> None:
        self._active_runs: dict[str, WorkflowRun] = {}

    def generate_workflow(self, plan: ExecutionPlan) -> WorkflowYAML:
        """Generate a GitHub Actions workflow YAML from an execution plan."""
        # Build the agent steps section
        agent_steps = []
        for step in plan.steps:
            step_name = step.get("name", "unnamed_step")
            step_cmd = step.get("command", "echo 'step executed'")
            agent_steps.append(f"echo '--- {step_name} ---'\n          {step_cmd}")

        steps_text = "\n          ".join(agent_steps) if agent_steps else "echo 'no steps defined'"

        yaml_content = self.WORKFLOW_TEMPLATE.format(
            task_id=plan.task_id,
            agent_steps=steps_text,
        )

        return WorkflowYAML(
            content=yaml_content,
            filename=f"aep-task-{plan.task_id}.yml",
            task_id=plan.task_id,
        )

    async def trigger_workflow(
        self,
        repo: dict,
        workflow: WorkflowYAML,
        inputs: WorkflowInputs,
    ) -> WorkflowRun:
        """Trigger a workflow in a GitHub repository.

        In production, this:
        1. Commits the workflow YAML to the repo's .github/workflows/
        2. Calls the workflow_dispatch API
        3. Returns the run ID
        """
        from app.integrations.github_client import GitHubClient, GitHubAuth, Repository
        from app.core.config import settings

        github_token = getattr(settings, "github_token", "") or ""
        if not github_token:
            log.warning("gha.no_token", task_id=workflow.task_id)
            return WorkflowRun(id="", status="failed")

        auth = GitHubAuth.pat(github_token)
        client = GitHubClient(auth)
        repository = Repository(
            owner=repo.get("owner", ""),
            repo=repo.get("repo", ""),
            default_branch=repo.get("default_branch", "main"),
        )

        try:
            # Commit the workflow file
            await client.push_changes(
                repository,
                repository.default_branch,
                [__import__("app.integrations.github_client", fromlist=["FileChange"]).FileChange(
                    path=f".github/workflows/{workflow.filename}",
                    content=workflow.content,
                )],
            )

            # Trigger the workflow
            run = await client.trigger_workflow(
                repository,
                workflow.filename,
                repository.default_branch,
                {
                    "task_payload": inputs.task_payload,
                    "execution_id": inputs.execution_id,
                    **inputs.extra,
                },
            )

            self._active_runs[run.id] = run
            log.info("gha.workflow_triggered", task_id=workflow.task_id, run_id=run.id)
            return run

        finally:
            await client.close()

    async def stream_logs(self, repo: dict, run_id: str) -> AsyncIterator[str]:
        """Stream logs from a running workflow."""
        from app.integrations.github_client import GitHubClient, GitHubAuth, Repository
        from app.core.config import settings

        github_token = getattr(settings, "github_token", "") or ""
        if not github_token:
            yield "[No GitHub token configured]"
            return

        auth = GitHubAuth.pat(github_token)
        client = GitHubClient(auth)
        repository = Repository(owner=repo.get("owner", ""), repo=repo.get("repo", ""))

        try:
            async for chunk in client.stream_workflow_logs(repository, run_id):
                yield chunk
        finally:
            await client.close()

    async def wait_for_completion(self, repo: dict, run_id: str, timeout_ms: int = 1_800_000) -> WorkflowResult:
        """Wait for a workflow to complete, polling every 4 seconds."""
        from app.integrations.github_client import GitHubClient, GitHubAuth, Repository
        from app.core.config import settings

        github_token = getattr(settings, "github_token", "") or ""
        if not github_token:
            return WorkflowResult(run_id=run_id, status="failed", conclusion="error")

        auth = GitHubAuth.pat(github_token)
        client = GitHubClient(auth)
        repository = Repository(owner=repo.get("owner", ""), repo=repo.get("repo", ""))

        start = time.time()
        timeout_s = timeout_ms / 1000

        try:
            while True:
                status = await client.get_workflow_run(repository, run_id)
                if status.status in ("completed", "success", "failure", "cancelled"):
                    artifacts = await client.download_artifacts(repository, run_id)
                    return WorkflowResult(
                        run_id=run_id,
                        status=status.status,
                        conclusion=status.conclusion,
                        artifacts=artifacts.artifacts,
                        duration_seconds=int(time.time() - start),
                    )
                if time.time() - start > timeout_s:
                    await client.cancel_workflow(repository, run_id)
                    return WorkflowResult(run_id=run_id, status="timeout", conclusion="cancelled")
                await __import__("asyncio").sleep(4)
        finally:
            await client.close()

    async def cancel_workflow(self, repo: dict, run_id: str) -> None:
        """Cancel a running workflow."""
        from app.integrations.github_client import GitHubClient, GitHubAuth, Repository
        from app.core.config import settings

        github_token = getattr(settings, "github_token", "") or ""
        auth = GitHubAuth.pat(github_token)
        client = GitHubClient(auth)
        repository = Repository(owner=repo.get("owner", ""), repo=repo.get("repo", ""))

        try:
            await client.cancel_workflow(repository, run_id)
            if run_id in self._active_runs:
                self._active_runs[run_id].status = "cancelled"
        finally:
            await client.close()

    async def retrieve_artifacts(self, repo: dict, run_id: str) -> ArtifactBundle:
        """Retrieve artifacts from a completed workflow."""
        from app.integrations.github_client import GitHubClient, GitHubAuth, Repository
        from app.core.config import settings

        github_token = getattr(settings, "github_token", "") or ""
        auth = GitHubAuth.pat(github_token)
        client = GitHubClient(auth)
        repository = Repository(owner=repo.get("owner", ""), repo=repo.get("repo", ""))

        try:
            bundle = await client.download_artifacts(repository, run_id)
            return bundle
        finally:
            await client.close()

    async def retry_workflow(self, execution_id: str, repo: dict, workflow: WorkflowYAML, inputs: WorkflowInputs) -> WorkflowRun:
        """Retry a failed workflow by re-triggering it."""
        log.info("gha.retry", execution_id=execution_id)
        return await self.trigger_workflow(repo, workflow, inputs)


# Singleton
gha_runtime = GHARuntimeManager()
