"""Execution service — Phase 3.

Orchestrates the full lifecycle of a single autonomous task:

1. Create execution record (PENDING)
2. Run Planner → produce ExecutionPlan (PLANNING)
3. Wait for approval when ``human_approval_required`` is true
   (AWAITING_APPROVAL)
4. Run Coder + optional GHA steps (EXECUTING)
5. Terminal state (COMPLETED / FAILED / CANCELLED)
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.aep.execution.state_machine import ExecutionStateMachine, InvalidTransitionError
from app.aep.feature_flags import get_feature_flag_service
from app.aep.models import (
    AepAgentPlan,
    AepExecution,
    AepExecutionState,
    AepExecutionStep,
    AepStepState,
)
from app.aep.observability import aep_logger
from app.aep.plugins import get_plugin_registry
from app.aep.plugins.types import AgentInput

_logger = aep_logger("aep.execution.service")


class ExecutionService:
    """High-level orchestrator for AEP task executions."""

    async def submit_task(
        self,
        *,
        tenant_id: uuid.UUID,
        title: str,
        description: str,
        repository_id: Optional[uuid.UUID] = None,
        branch: Optional[str] = None,
        created_by: Optional[uuid.UUID] = None,
        db: AsyncSession,
    ) -> dict[str, Any]:
        """Create a new execution in PENDING state."""
        execution = AepExecution(
            tenant_id=tenant_id,
            title=title,
            description=description,
            repository_id=repository_id,
            branch=branch,
            created_by=created_by,
            state=AepExecutionState.PENDING.value,
        )
        db.add(execution)
        await db.commit()
        await db.refresh(execution)

        _logger.info(
            "execution_created",
            execution_id=str(execution.id),
            tenant_id=str(tenant_id),
            title=title,
        )
        return _execution_to_dict(execution)

    async def run_planning(
        self,
        execution_id: uuid.UUID,
        *,
        db: AsyncSession,
    ) -> dict[str, Any]:
        """Transition to PLANNING and invoke the Planner agent."""
        execution = await self._get_execution(execution_id, db)
        fsm = ExecutionStateMachine(execution.state)

        await fsm.transition(
            AepExecutionState.PLANNING.value,
            tenant_id=str(execution.tenant_id),
            task_id=str(execution.id),
        )
        execution.state = fsm.state
        execution.started_at = datetime.now(timezone.utc)
        await db.commit()

        registry = get_plugin_registry()
        planner = registry.get("planner")
        if planner is None:
            await self._fail_execution(
                execution, "Planner agent not available", db=db
            )
            return _execution_to_dict(execution)

        agent_input = AgentInput(
            tenant_id=execution.tenant_id,
            execution_id=execution.id,
            step_index=0,
            repository_id=execution.repository_id,
            branch=execution.branch,
            task_description=execution.description or execution.title,
        )

        step = AepExecutionStep(
            execution_id=execution.id,
            tenant_id=execution.tenant_id,
            step_index=0,
            agent_name="planner",
            state=AepStepState.RUNNING.value,
            input=agent_input.model_dump(mode="json"),
            started_at=datetime.now(timezone.utc),
        )
        db.add(step)
        await db.commit()

        output = await planner.execute(agent_input)

        step.state = AepStepState.SUCCEEDED.value if output.success else AepStepState.FAILED.value
        step.output = output.result
        step.error = output.error
        step.token_input = output.token_input
        step.token_output = output.token_output
        step.duration_ms = int(output.duration_ms)
        step.completed_at = datetime.now(timezone.utc)
        await db.commit()

        if not output.success:
            await self._fail_execution(
                execution, output.error or "Planning failed", db=db,
            )
            return _execution_to_dict(execution)

        plan_record = AepAgentPlan(
            execution_id=execution.id,
            tenant_id=execution.tenant_id,
            plan=output.result,
            estimated_tokens=output.result.get("estimated_tokens", 0),
            estimated_steps=len(output.result.get("steps", [])),
            requires_github_actions=output.result.get("requires_github_actions", False),
        )
        db.add(plan_record)

        ff = get_feature_flag_service()
        needs_approval = await ff.is_enabled(
            "human_approval_required", tenant_id=execution.tenant_id, db=db,
        )

        if needs_approval:
            await fsm.transition(
                AepExecutionState.AWAITING_APPROVAL.value,
                tenant_id=str(execution.tenant_id),
                task_id=str(execution.id),
            )
        else:
            await fsm.transition(
                AepExecutionState.AWAITING_APPROVAL.value,
                tenant_id=str(execution.tenant_id),
                task_id=str(execution.id),
            )

        execution.state = fsm.state
        execution.token_input += output.token_input
        execution.token_output += output.token_output
        await db.commit()

        return _execution_to_dict(execution)

    async def approve_execution(
        self,
        execution_id: uuid.UUID,
        *,
        actor_id: Optional[str] = None,
        db: AsyncSession,
    ) -> dict[str, Any]:
        """Approve a plan and transition to EXECUTING."""
        execution = await self._get_execution(execution_id, db)
        fsm = ExecutionStateMachine(execution.state)

        await fsm.transition(
            AepExecutionState.EXECUTING.value,
            tenant_id=str(execution.tenant_id),
            task_id=str(execution.id),
            actor_type="human",
            actor_id=actor_id,
            reason="Plan approved",
        )
        execution.state = fsm.state
        await db.commit()

        return _execution_to_dict(execution)

    async def reject_execution(
        self,
        execution_id: uuid.UUID,
        *,
        reason: str = "Plan rejected by operator",
        actor_id: Optional[str] = None,
        db: AsyncSession,
    ) -> dict[str, Any]:
        """Reject a plan and cancel the execution."""
        execution = await self._get_execution(execution_id, db)
        fsm = ExecutionStateMachine(execution.state)

        await fsm.transition(
            AepExecutionState.CANCELLED.value,
            tenant_id=str(execution.tenant_id),
            task_id=str(execution.id),
            actor_type="human",
            actor_id=actor_id,
            reason=reason,
        )
        execution.state = fsm.state
        execution.error = reason
        execution.completed_at = datetime.now(timezone.utc)
        await db.commit()

        return _execution_to_dict(execution)

    async def run_execution(
        self,
        execution_id: uuid.UUID,
        *,
        db: AsyncSession,
    ) -> dict[str, Any]:
        """Execute the plan steps (Coder agent). Must be in EXECUTING state."""
        execution = await self._get_execution(execution_id, db)
        if execution.state != AepExecutionState.EXECUTING.value:
            raise InvalidTransitionError(execution.state, "run_execution requires EXECUTING state")

        registry = get_plugin_registry()
        coder = registry.get("coder")
        if coder is None:
            await self._fail_execution(execution, "Coder agent not available", db=db)
            return _execution_to_dict(execution)

        plan_result = await db.execute(
            select(AepAgentPlan)
            .where(AepAgentPlan.execution_id == execution_id)
            .order_by(AepAgentPlan.version.desc())
        )
        plan_record = plan_result.scalar_one_or_none()
        plan_data = plan_record.plan if plan_record else {}
        steps = plan_data.get("steps", [])

        coder_steps = [s for s in steps if s.get("agent_name") == "coder"]
        if not coder_steps:
            coder_steps = [{"step_index": 1, "agent_name": "coder", "description": "Generate code"}]

        for plan_step in coder_steps:
            step_index = plan_step.get("step_index", 1)
            agent_input = AgentInput(
                tenant_id=execution.tenant_id,
                execution_id=execution.id,
                step_index=step_index,
                repository_id=execution.repository_id,
                branch=execution.branch,
                task_description=execution.description or execution.title,
                upstream=plan_data,
            )

            step = AepExecutionStep(
                execution_id=execution.id,
                tenant_id=execution.tenant_id,
                step_index=step_index,
                agent_name="coder",
                state=AepStepState.RUNNING.value,
                input=agent_input.model_dump(mode="json"),
                started_at=datetime.now(timezone.utc),
            )
            db.add(step)
            await db.commit()

            output = await coder.execute(agent_input)

            step.state = AepStepState.SUCCEEDED.value if output.success else AepStepState.FAILED.value
            step.output = output.result
            step.error = output.error
            step.token_input = output.token_input
            step.token_output = output.token_output
            step.duration_ms = int(output.duration_ms)
            step.completed_at = datetime.now(timezone.utc)

            execution.token_input += output.token_input
            execution.token_output += output.token_output
            await db.commit()

            if not output.success:
                await self._fail_execution(
                    execution, output.error or "Coding step failed", db=db,
                )
                return _execution_to_dict(execution)

        fsm = ExecutionStateMachine(execution.state)
        await fsm.transition(
            AepExecutionState.VALIDATING.value,
            tenant_id=str(execution.tenant_id),
            task_id=str(execution.id),
        )
        await fsm.transition(
            AepExecutionState.COMPLETED.value,
            tenant_id=str(execution.tenant_id),
            task_id=str(execution.id),
        )
        execution.state = fsm.state
        execution.completed_at = datetime.now(timezone.utc)
        await db.commit()

        _logger.info(
            "execution_completed",
            execution_id=str(execution.id),
        )
        return _execution_to_dict(execution)

    async def get_execution(
        self, execution_id: uuid.UUID, *, db: AsyncSession,
    ) -> dict[str, Any]:
        execution = await self._get_execution(execution_id, db)
        return _execution_to_dict(execution)

    async def list_executions(
        self,
        tenant_id: uuid.UUID,
        *,
        db: AsyncSession,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        result = await db.execute(
            select(AepExecution)
            .where(AepExecution.tenant_id == tenant_id)
            .order_by(AepExecution.created_at.desc())
            .limit(limit)
        )
        return [_execution_to_dict(e) for e in result.scalars().all()]

    async def list_steps(
        self,
        execution_id: uuid.UUID,
        *,
        db: AsyncSession,
    ) -> list[dict[str, Any]]:
        """List all steps for a given execution, ordered by step_index."""
        await self._get_execution(execution_id, db)
        result = await db.execute(
            select(AepExecutionStep)
            .where(AepExecutionStep.execution_id == execution_id)
            .order_by(AepExecutionStep.step_index)
        )
        return [_step_to_dict(s) for s in result.scalars().all()]

    # ── internal helpers ─────────────────────────────────────────────

    async def _get_execution(
        self, execution_id: uuid.UUID, db: AsyncSession,
    ) -> AepExecution:
        result = await db.execute(
            select(AepExecution).where(AepExecution.id == execution_id)
        )
        execution = result.scalar_one_or_none()
        if execution is None:
            raise ValueError(f"Execution {execution_id} not found")
        return execution

    async def _fail_execution(
        self,
        execution: AepExecution,
        error: str,
        *,
        db: AsyncSession,
    ) -> None:
        fsm = ExecutionStateMachine(execution.state)
        if fsm.can_transition(AepExecutionState.FAILED.value):
            await fsm.transition(
                AepExecutionState.FAILED.value,
                tenant_id=str(execution.tenant_id),
                task_id=str(execution.id),
                reason=error,
            )
            execution.state = fsm.state
        execution.error = error
        execution.completed_at = datetime.now(timezone.utc)
        await db.commit()
        _logger.warning(
            "execution_failed",
            execution_id=str(execution.id),
            error=error,
        )


def _execution_to_dict(e: AepExecution) -> dict[str, Any]:
    return {
        "id": str(e.id),
        "tenant_id": str(e.tenant_id),
        "title": e.title,
        "description": e.description,
        "state": e.state,
        "branch": e.branch,
        "token_input": e.token_input,
        "token_output": e.token_output,
        "error": e.error,
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "started_at": e.started_at.isoformat() if e.started_at else None,
        "completed_at": e.completed_at.isoformat() if e.completed_at else None,
    }


def _step_to_dict(s: AepExecutionStep) -> dict[str, Any]:
    return {
        "id": str(s.id),
        "execution_id": str(s.execution_id),
        "step_index": s.step_index,
        "agent_name": s.agent_name,
        "model": s.model,
        "state": s.state,
        "error": s.error,
        "token_input": s.token_input,
        "token_output": s.token_output,
        "duration_ms": s.duration_ms,
        "started_at": s.started_at.isoformat() if s.started_at else None,
        "completed_at": s.completed_at.isoformat() if s.completed_at else None,
    }


_singleton: Optional[ExecutionService] = None


def get_execution_service() -> ExecutionService:
    global _singleton
    if _singleton is None:
        _singleton = ExecutionService()
    return _singleton
