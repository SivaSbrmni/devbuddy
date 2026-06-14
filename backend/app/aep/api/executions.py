"""Execution API — Phase 3.

Task submission, approval gate, and execution status.

Routes:
    POST   /api/v1/aep/executions            — submit a task
    GET    /api/v1/aep/executions            — list executions
    GET    /api/v1/aep/executions/{id}       — get execution detail
    POST   /api/v1/aep/executions/{id}/plan  — trigger planning
    POST   /api/v1/aep/executions/{id}/approve — approve plan
    POST   /api/v1/aep/executions/{id}/reject  — reject plan
    POST   /api/v1/aep/executions/{id}/execute — run execution
"""
from __future__ import annotations

import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.aep.execution.service import get_execution_service
from app.aep.execution.state_machine import InvalidTransitionError
from app.aep.observability import aep_logger
from app.core.database import get_db
from app.core.security import get_current_user

router = APIRouter(prefix="/aep/executions", tags=["aep-executions"])
_logger = aep_logger("aep.api.executions")


# ─────────────────────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────────────────────


class TaskSubmission(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: str = Field(..., min_length=1)
    repository_id: Optional[uuid.UUID] = None
    branch: Optional[str] = None


class ExecutionOut(BaseModel):
    id: str
    tenant_id: str
    title: str
    description: Optional[str]
    state: str
    branch: Optional[str]
    token_input: int
    token_output: int
    error: Optional[str]
    created_at: Optional[str]
    started_at: Optional[str]
    completed_at: Optional[str]


class ExecutionListOut(BaseModel):
    executions: list[ExecutionOut]
    count: int


class RejectBody(BaseModel):
    reason: str = "Plan rejected by operator"


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _tenant_id(user: dict[str, Any]) -> uuid.UUID:
    payload = user.get("payload") or {}
    tid = payload.get("tenant_id") or payload.get("sub")
    return uuid.UUID(str(tid))


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────


@router.post("", response_model=ExecutionOut, status_code=status.HTTP_201_CREATED)
async def submit_task(
    body: TaskSubmission,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExecutionOut:
    """Submit a new task for autonomous execution."""
    svc = get_execution_service()
    result = await svc.submit_task(
        tenant_id=_tenant_id(user),
        title=body.title,
        description=body.description,
        repository_id=body.repository_id,
        branch=body.branch,
        created_by=uuid.UUID(user["id"]),
        db=db,
    )
    return ExecutionOut(**result)


@router.get("", response_model=ExecutionListOut)
async def list_executions(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExecutionListOut:
    """List all executions for the current tenant."""
    svc = get_execution_service()
    executions = await svc.list_executions(_tenant_id(user), db=db)
    return ExecutionListOut(
        executions=[ExecutionOut(**e) for e in executions],
        count=len(executions),
    )


@router.get("/{execution_id}", response_model=ExecutionOut)
async def get_execution(
    execution_id: uuid.UUID,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExecutionOut:
    """Get execution detail."""
    svc = get_execution_service()
    try:
        result = await svc.get_execution(execution_id, db=db)
    except ValueError:
        raise HTTPException(status_code=404, detail="Execution not found")
    return ExecutionOut(**result)


@router.get("/{execution_id}/steps")
async def list_execution_steps(
    execution_id: uuid.UUID,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """List all steps for an execution."""
    svc = get_execution_service()
    try:
        steps = await svc.list_steps(execution_id, db=db)
    except ValueError:
        raise HTTPException(status_code=404, detail="Execution not found")
    return {"steps": steps, "count": len(steps)}


@router.post("/{execution_id}/plan", response_model=ExecutionOut)
async def trigger_planning(
    execution_id: uuid.UUID,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExecutionOut:
    """Trigger planning for a submitted task."""
    svc = get_execution_service()
    try:
        result = await svc.run_planning(execution_id, db=db)
    except (ValueError, InvalidTransitionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return ExecutionOut(**result)


@router.post("/{execution_id}/approve", response_model=ExecutionOut)
async def approve_plan(
    execution_id: uuid.UUID,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExecutionOut:
    """Approve an execution plan. Transitions from AWAITING_APPROVAL to EXECUTING."""
    svc = get_execution_service()
    try:
        result = await svc.approve_execution(
            execution_id, actor_id=user.get("id"), db=db,
        )
    except (ValueError, InvalidTransitionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return ExecutionOut(**result)


@router.post("/{execution_id}/reject", response_model=ExecutionOut)
async def reject_plan(
    execution_id: uuid.UUID,
    body: RejectBody,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExecutionOut:
    """Reject an execution plan. Cancels the execution."""
    svc = get_execution_service()
    try:
        result = await svc.reject_execution(
            execution_id, reason=body.reason, actor_id=user.get("id"), db=db,
        )
    except (ValueError, InvalidTransitionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return ExecutionOut(**result)


@router.post("/{execution_id}/execute", response_model=ExecutionOut)
async def run_execution(
    execution_id: uuid.UUID,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExecutionOut:
    """Run the execution (Coder agent). Must be in EXECUTING state."""
    svc = get_execution_service()
    try:
        result = await svc.run_execution(execution_id, db=db)
    except (ValueError, InvalidTransitionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return ExecutionOut(**result)
