"""Project CRUD + pipeline endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.model_router import model_router
from app.models.project import Project
from app.models.task import Task
from app.schemas.project import (
    CodingTaskRequest,
    PipelineRequest,
    ProjectCreate,
    ProjectOut,
    ProjectUpdate,
    TaskOut,
)

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectOut, status_code=201)
async def create_project(body: ProjectCreate, db: AsyncSession = Depends(get_db)) -> ProjectOut:
    project = Project(**body.model_dump())
    db.add(project)
    await db.flush()
    return ProjectOut.model_validate(project)


@router.get("", response_model=list[ProjectOut])
async def list_projects(db: AsyncSession = Depends(get_db)) -> list[ProjectOut]:
    result = await db.execute(select(Project).order_by(Project.created_at.desc()))
    projects = list(result.scalars().all())
    return [ProjectOut.model_validate(p) for p in projects]


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(project_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> ProjectOut:
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(404, "Project not found")
    return ProjectOut.model_validate(project)


@router.patch("/{project_id}", response_model=ProjectOut)
async def update_project(
    project_id: uuid.UUID, body: ProjectUpdate, db: AsyncSession = Depends(get_db)
) -> ProjectOut:
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(404, "Project not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    await db.flush()
    return ProjectOut.model_validate(project)


@router.delete("/{project_id}", status_code=204, response_model=None)
async def delete_project(project_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> None:
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(404, "Project not found")
    await db.delete(project)


# ── Pipeline Endpoints ──────────────────────────────────────────────
@router.post("/{project_id}/pipeline", status_code=202)
async def run_pipeline(
    project_id: uuid.UUID,
    body: PipelineRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Run requirements → analysis → planning → architecture pipeline."""
    from app.agents.orchestrator import TaskOrchestrator

    # Verify project exists
    result = await db.execute(select(Project).where(Project.id == project_id))
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Project not found")

    # Create a task record
    task = Task(
        project_id=project_id,
        title="Pipeline: Analysis → Plan → Architecture",
        task_type="planning",
    )
    db.add(task)
    await db.flush()

    orchestrator = TaskOrchestrator(db, model_router)
    try:
        results = await orchestrator.run_pipeline(
            project_id, task.id, body.requirements, body.tech_stack
        )
    except RuntimeError as exc:
        task.status = "failed"
        task.result = {"error": str(exc)}
        await db.flush()
        raise HTTPException(503, detail=str(exc))
    except Exception as exc:
        task.status = "failed"
        task.result = {"error": str(exc)}
        await db.flush()
        raise HTTPException(500, detail=f"Pipeline failed: {exc}")

    task.status = "completed"
    task.result = results
    await db.flush()

    return {"task_id": str(task.id), "status": "completed", "results": results}


@router.post("/{project_id}/code", status_code=202)
async def run_coding_task(
    project_id: uuid.UUID,
    body: CodingTaskRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Execute a coding task: code → review → test."""
    from app.agents.orchestrator import TaskOrchestrator

    result = await db.execute(select(Project).where(Project.id == project_id))
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Project not found")

    task = Task(
        project_id=project_id,
        title=f"Code: {body.task_description[:80]}",
        task_type="coding",
    )
    db.add(task)
    await db.flush()

    orchestrator = TaskOrchestrator(db, model_router)
    try:
        results = await orchestrator.run_coding_task(
            project_id, task.id, body.task_description, body.file_path, body.existing_code
        )
    except RuntimeError as exc:
        task.status = "failed"
        task.result = {"error": str(exc)}
        await db.flush()
        raise HTTPException(503, detail=str(exc))
    except Exception as exc:
        task.status = "failed"
        task.result = {"error": str(exc)}
        await db.flush()
        raise HTTPException(500, detail=f"Coding task failed: {exc}")

    task.status = "completed"
    task.result = results
    await db.flush()

    return {"task_id": str(task.id), "status": "completed", "results": results}


# ── Tasks ───────────────────────────────────────────────────────────
@router.get("/{project_id}/tasks", response_model=list[TaskOut])
async def list_tasks(project_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> list[TaskOut]:
    result = await db.execute(
        select(Task).where(Task.project_id == project_id).order_by(Task.created_at.desc())
    )
    tasks = list(result.scalars().all())
    return [TaskOut.model_validate(t) for t in tasks]
