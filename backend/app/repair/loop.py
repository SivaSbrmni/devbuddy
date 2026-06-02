"""Autonomous Repair Loop — THE MOST IMPORTANT REQUIREMENT.

Generate → Commit → Execute → Collect Logs → Analyze Failure →
Generate Fix → Commit Patch → Retry → Repeat

Stops only when:
- Success achieved
- Retry limit reached
- Human approval required

The system must NEVER stop at the first failure.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.execution_controller import ExecutionController
from app.agents.fix_agent import FixAgent
from app.core.config import settings
from app.core.model_router import ModelRouter
from app.execution.github_actions import ExecutionManager, GitHubActionsClient
from app.models.execution import DebugExperiment, Run
from app.workspace.manager import WorkspaceManager

log = structlog.get_logger()


class RepairLoop:
    """The autonomous repair loop — generates, tests, fixes, retries.

    This is the heart of the system. Without it, the platform is considered a failure.
    """

    def __init__(
        self,
        db: AsyncSession,
        router: ModelRouter,
        workspace: WorkspaceManager,
        execution: ExecutionManager,
        github: GitHubActionsClient,
    ) -> None:
        self.db = db
        self.router = router
        self.workspace = workspace
        self.execution = execution
        self.github = github
        self.fix_agent = FixAgent(router, db)
        self.exec_controller = ExecutionController(router, db)

    async def run_repair_cycle(
        self,
        project_id: uuid.UUID,
        task_id: uuid.UUID,
        workspace_id: str,
        *,
        owner: str,
        repo: str,
        branch: str,
        initial_run: Run | None = None,
    ) -> dict[str, Any]:
        """Execute the full repair loop until success or limit reached."""
        max_retries = settings.MAX_REPAIR_RETRIES
        attempt = 0
        previous_attempts: list[dict[str, Any]] = []
        current_run = initial_run

        while attempt < max_retries:
            attempt += 1
            log.info(
                "repair_loop.attempt",
                attempt=attempt,
                max_retries=max_retries,
                project_id=str(project_id),
            )

            # Step 1: If we have a run, collect evidence
            if current_run:
                # Wait for any running workflow
                workflow_runs = await self.github.get_workflow_runs(owner, repo, branch=branch, limit=1)
                if workflow_runs:
                    gh_run = workflow_runs[0]
                    if gh_run.get("status") != "completed":
                        gh_run = await self.github.wait_for_run(owner, repo, gh_run["id"])

                    # Collect evidence
                    evidence = await self.execution.collect_evidence(owner, repo, current_run, gh_run["id"])

                    if evidence["conclusion"] == "success":
                        log.info("repair_loop.success", attempt=attempt)
                        current_run.status = "success"
                        await self.db.flush()
                        return {
                            "status": "success",
                            "attempts": attempt,
                            "message": "All checks passed",
                        }

            # Step 2: Gather all evidence for the fix agent
            failure_logs = ""
            stack_trace = ""
            if current_run:
                from sqlalchemy import select
                from app.models.execution import Artifact

                stmt = select(Artifact).where(Artifact.run_id == current_run.id)
                result = await self.db.execute(stmt)
                artifacts = result.scalars().all()
                for art in artifacts:
                    if art.artifact_type == "log":
                        failure_logs += art.content + "\n"
                    if art.artifact_type == "error_trace":
                        stack_trace += art.content + "\n"

            # Step 3: Read source code from workspace
            files = await self.workspace.list_files(workspace_id)
            source_snippets: list[str] = []
            for f in files[:20]:  # limit to first 20 files
                try:
                    content = await self.workspace.read_file(workspace_id, f)
                    source_snippets.append(f"--- {f} ---\n{content[:2000]}")
                except Exception:
                    pass
            source_code = "\n".join(source_snippets)

            # Step 4: Fix Agent analyzes and generates fix
            fix_result = await self.fix_agent.run(
                task_id,
                {
                    "failure_logs": failure_logs,
                    "stack_trace": stack_trace,
                    "source_code": source_code,
                    "previous_attempts": previous_attempts,
                    "evidence": {"attempt": attempt, "files": files},
                },
            )

            # Step 5: Record experiment
            experiment = DebugExperiment(
                run_id=current_run.id if current_run else uuid.uuid4(),
                project_id=project_id,
                failure_signature=stack_trace[:500],
                hypothesis=str(fix_result.get("analysis", ""))[:500],
                evidence={"attempt": attempt, "logs_excerpt": failure_logs[:1000]},
                fix_applied=str(fix_result.get("analysis", ""))[:2000],
            )
            self.db.add(experiment)
            await self.db.flush()

            # Step 6: Apply fix (parse the fix agent output)
            try:
                analysis = json.loads(fix_result.get("analysis", "{}"))
                fix_data = analysis.get("fix", {})
                fix_files = fix_data.get("files", [])
                for fix_file in fix_files:
                    path = fix_file.get("path", "")
                    patched = fix_file.get("patched", "")
                    if path and patched:
                        await self.workspace.write_file(workspace_id, path, patched)
                        log.info("repair_loop.patched", path=path)
            except (json.JSONDecodeError, KeyError) as exc:
                log.warning("repair_loop.parse_failed", error=str(exc))

            # Step 7: Commit and push the fix
            commit_result = await self.workspace.commit_and_push(
                workspace_id,
                f"fix: repair attempt {attempt}",
                branch=branch,
            )

            previous_attempts.append({
                "attempt": attempt,
                "fix": str(fix_result.get("analysis", ""))[:500],
                "commit_exit_code": commit_result.exit_code,
            })

            # Step 8: Create new run record for retry
            current_run = await self.execution.create_run(
                project_id,
                "repair",
                task_id=task_id,
                config={"attempt": attempt, "retry_of": str(current_run.id) if current_run else None},
            )
            current_run.retry_count = attempt

            # Wait briefly for GitHub Actions to pick up the push
            import asyncio
            await asyncio.sleep(10)

        # Exhausted retries
        log.warning("repair_loop.exhausted", attempts=max_retries)
        return {
            "status": "exhausted",
            "attempts": max_retries,
            "message": f"Failed after {max_retries} repair attempts — human review required",
            "previous_attempts": previous_attempts,
        }
