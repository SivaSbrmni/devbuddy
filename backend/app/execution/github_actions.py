"""GitHub Actions integration — trigger workflows, collect artifacts, evaluate results.

GitHub is the source of truth:
Agent → Commit → Push → GitHub Actions → Artifact Collection → Evaluation → Repair Loop
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.execution import Artifact, Run, WorkflowRun

log = structlog.get_logger()


class GitHubActionsClient:
    """Interact with GitHub Actions API."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def startup(self) -> None:
        if settings.GITHUB_TOKEN:
            self._client = httpx.AsyncClient(
                base_url="https://api.github.com",
                headers={
                    "Authorization": f"token {settings.GITHUB_TOKEN}",
                    "Accept": "application/vnd.github+json",
                },
                timeout=60.0,
            )

    async def shutdown(self) -> None:
        if self._client:
            await self._client.aclose()

    async def trigger_workflow(
        self, owner: str, repo: str, workflow_id: str, ref: str = "main", inputs: dict | None = None
    ) -> dict[str, Any]:
        if not self._client:
            raise RuntimeError("GitHub client not configured")
        resp = await self._client.post(
            f"/repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches",
            json={"ref": ref, "inputs": inputs or {}},
        )
        resp.raise_for_status()
        return {"status": "dispatched", "ref": ref}

    async def get_workflow_runs(
        self, owner: str, repo: str, *, branch: str | None = None, limit: int = 5
    ) -> list[dict[str, Any]]:
        if not self._client:
            raise RuntimeError("GitHub client not configured")
        params: dict[str, Any] = {"per_page": limit}
        if branch:
            params["branch"] = branch
        resp = await self._client.get(f"/repos/{owner}/{repo}/actions/runs", params=params)
        resp.raise_for_status()
        return resp.json().get("workflow_runs", [])

    async def get_run_logs(self, owner: str, repo: str, run_id: int) -> str:
        if not self._client:
            raise RuntimeError("GitHub client not configured")
        resp = await self._client.get(
            f"/repos/{owner}/{repo}/actions/runs/{run_id}/logs",
            follow_redirects=True,
        )
        if resp.status_code == 200:
            return resp.text[:50000]  # cap
        return f"Failed to fetch logs: {resp.status_code}"

    async def get_run_jobs(self, owner: str, repo: str, run_id: int) -> list[dict[str, Any]]:
        if not self._client:
            raise RuntimeError("GitHub client not configured")
        resp = await self._client.get(f"/repos/{owner}/{repo}/actions/runs/{run_id}/jobs")
        resp.raise_for_status()
        return resp.json().get("jobs", [])

    async def wait_for_run(
        self, owner: str, repo: str, run_id: int, *, poll_interval: int = 15, max_wait: int = 600
    ) -> dict[str, Any]:
        """Poll until a workflow run completes."""
        if not self._client:
            raise RuntimeError("GitHub client not configured")
        elapsed = 0
        while elapsed < max_wait:
            resp = await self._client.get(f"/repos/{owner}/{repo}/actions/runs/{run_id}")
            resp.raise_for_status()
            data = resp.json()
            status = data.get("status")
            if status == "completed":
                return data
            log.debug("github.waiting", run_id=run_id, status=status, elapsed=elapsed)
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval
        return {"status": "timeout", "run_id": run_id}


class ExecutionManager:
    """Orchestrates execution runs, collects artifacts, persists results."""

    def __init__(self, db: AsyncSession, github: GitHubActionsClient) -> None:
        self.db = db
        self.github = github

    async def create_run(
        self,
        project_id: uuid.UUID,
        run_type: str,
        task_id: uuid.UUID | None = None,
        config: dict | None = None,
    ) -> Run:
        run = Run(
            project_id=project_id,
            task_id=task_id,
            run_type=run_type,
            config=config or {},
        )
        self.db.add(run)
        await self.db.flush()
        return run

    async def record_workflow(
        self,
        run_id: uuid.UUID,
        github_run_id: int,
        workflow_name: str,
    ) -> WorkflowRun:
        wf = WorkflowRun(
            run_id=run_id,
            github_run_id=github_run_id,
            workflow_name=workflow_name,
        )
        self.db.add(wf)
        await self.db.flush()
        return wf

    async def store_artifact(
        self,
        run_id: uuid.UUID,
        artifact_type: str,
        name: str,
        content: str,
        metadata: dict | None = None,
    ) -> Artifact:
        art = Artifact(
            run_id=run_id,
            artifact_type=artifact_type,
            name=name,
            content=content,
            metadata_=metadata or {},
        )
        self.db.add(art)
        await self.db.flush()
        return art

    async def collect_evidence(
        self,
        owner: str,
        repo: str,
        run: Run,
        github_run_id: int,
    ) -> dict[str, Any]:
        """Collect all evidence from a GitHub Actions run."""
        jobs = await self.github.get_run_jobs(owner, repo, github_run_id)
        logs = await self.github.get_run_logs(owner, repo, github_run_id)

        # Store artifacts
        await self.store_artifact(run.id, "log", "workflow_logs", logs)

        failed_jobs = [j for j in jobs if j.get("conclusion") == "failure"]
        for job in failed_jobs:
            await self.store_artifact(
                run.id,
                "error_trace",
                f"failed_job_{job.get('name', 'unknown')}",
                str(job),
            )

        return {
            "total_jobs": len(jobs),
            "failed_jobs": len(failed_jobs),
            "logs_length": len(logs),
            "conclusion": "failure" if failed_jobs else "success",
        }


# Singletons
github_client = GitHubActionsClient()
