"""Execution, Repair, and Deployment API routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.model_router import model_router
from app.execution.github_actions import ExecutionManager, github_client
from app.models.execution import Run
from app.models.project import Project
from app.schemas.project import DeployRequest, RunOut

router = APIRouter(tags=["execution"])


# ── Runs ────────────────────────────────────────────────────────────
@router.get("/projects/{project_id}/runs", response_model=list[RunOut])
async def list_runs(
    project_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> list[RunOut]:
    result = await db.execute(
        select(Run).where(Run.project_id == project_id).order_by(Run.created_at.desc()).limit(50)
    )
    runs = list(result.scalars().all())
    return [RunOut.model_validate(r) for r in runs]


@router.post("/projects/{project_id}/runs", status_code=201)
async def create_run(
    project_id: uuid.UUID,
    run_type: str = "build",
    db: AsyncSession = Depends(get_db),
) -> dict:
    mgr = ExecutionManager(db, github_client)
    run = await mgr.create_run(project_id, run_type)
    return {"id": str(run.id), "status": run.status}


# ── Repair Loop ─────────────────────────────────────────────────────
@router.post("/projects/{project_id}/repair", status_code=202)
async def trigger_repair(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Trigger the autonomous repair loop for a failing project."""
    from app.repair.loop import RepairLoop
    from app.workspace.manager import workspace_manager

    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(404, "Project not found")
    if not project.repo_url:
        raise HTTPException(400, "Project has no repository configured")

    # Parse owner/repo from URL
    parts = project.repo_url.rstrip("/").split("/")
    owner, repo = parts[-2], parts[-1].replace(".git", "")

    exec_mgr = ExecutionManager(db, github_client)
    repair = RepairLoop(db, model_router, workspace_manager, exec_mgr, github_client)

    # Create workspace and initial run
    ws = await workspace_manager.create_workspace(str(project_id))
    run = await exec_mgr.create_run(project_id, "repair", task_id=task_id)

    repair_result = await repair.run_repair_cycle(
        project_id,
        task_id,
        ws.workspace_id,
        owner=owner,
        repo=repo,
        branch=project.repo_branch,
        initial_run=run,
    )

    return repair_result


# ── Deployment ──────────────────────────────────────────────────────
@router.post("/projects/{project_id}/deploy", status_code=202)
async def deploy_project(
    project_id: uuid.UUID,
    body: DeployRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.deployment.manager import DeploymentManager
    from app.workspace.manager import workspace_manager

    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(404, "Project not found")

    ws = await workspace_manager.create_workspace(str(project_id))
    mgr = DeploymentManager(db, workspace_manager)

    deploy_result = await mgr.deploy(
        project_id,
        body.provider,
        ws.workspace_id,
        {**body.config, "environment": body.environment, "version": body.version},
    )

    return deploy_result
