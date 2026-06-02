"""Continuous Improvement Engine — monitors, identifies, and feeds back improvements.

After deployment, continuously monitors logs, failures, errors, performance, tech debt.
Generates improvement tasks and feeds them back into planning.
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.improvement_agent import ImprovementAgent
from app.core.model_router import ModelRouter
from app.models.execution import DebugExperiment, Run
from app.models.memory import DeploymentHistory

log = structlog.get_logger()


class ContinuousImprovementEngine:
    """Scans project history and generates actionable improvement tasks."""

    def __init__(self, db: AsyncSession, router: ModelRouter) -> None:
        self.db = db
        self.router = router
        self.agent = ImprovementAgent(router, db)

    async def analyze_project(self, project_id: uuid.UUID, task_id: uuid.UUID) -> dict[str, Any]:
        """Run a full improvement analysis for a project."""

        # Gather project metrics
        metrics = await self._gather_metrics(project_id)
        recent_failures = await self._recent_failures(project_id)
        deployment_history = await self._deployment_summary(project_id)

        # Run the improvement agent
        result = await self.agent.run(
            task_id,
            {
                "project_metrics": metrics,
                "recent_failures": recent_failures,
                "deployment_history": deployment_history,
                "codebase_summary": "",  # populated by workspace if available
            },
        )

        return result

    async def _gather_metrics(self, project_id: uuid.UUID) -> dict[str, Any]:
        # Run success/failure counts
        stmt = select(Run).where(Run.project_id == project_id).order_by(Run.created_at.desc()).limit(50)
        result = await self.db.execute(stmt)
        runs = result.scalars().all()

        total = len(runs)
        successes = sum(1 for r in runs if r.status == "success")
        failures = sum(1 for r in runs if r.status == "failed")
        repairs = sum(1 for r in runs if r.run_type == "repair")

        return {
            "total_runs": total,
            "successes": successes,
            "failures": failures,
            "repair_runs": repairs,
            "success_rate": (successes / total * 100) if total > 0 else 0,
        }

    async def _recent_failures(self, project_id: uuid.UUID) -> list[dict[str, Any]]:
        stmt = (
            select(DebugExperiment)
            .where(DebugExperiment.project_id == project_id)
            .order_by(DebugExperiment.created_at.desc())
            .limit(10)
        )
        result = await self.db.execute(stmt)
        experiments = result.scalars().all()

        return [
            {
                "failure": exp.failure_signature[:200],
                "hypothesis": exp.hypothesis[:200],
                "outcome": exp.outcome,
            }
            for exp in experiments
        ]

    async def _deployment_summary(self, project_id: uuid.UUID) -> list[dict[str, Any]]:
        stmt = (
            select(DeploymentHistory)
            .where(DeploymentHistory.project_id == project_id)
            .order_by(DeploymentHistory.created_at.desc())
            .limit(10)
        )
        result = await self.db.execute(stmt)
        deploys = result.scalars().all()

        return [
            {
                "provider": d.provider,
                "status": d.status,
                "version": d.version,
                "deployed_at": d.deployed_at.isoformat() if d.deployed_at else None,
            }
            for d in deploys
        ]
