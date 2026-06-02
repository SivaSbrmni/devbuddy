"""Observability — metrics tracking, dashboards, and reports.

Tracks:
- Build / repair / deployment success rates
- Retry counts
- Token / model / cost metrics
- Runtime metrics, error rates
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.execution import Run
from app.models.memory import DeploymentHistory, ModelUsage

log = structlog.get_logger()


class MetricsCollector:
    """Collects and queries platform metrics."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def record_model_usage(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        latency_ms: int | None = None,
        project_id: uuid.UUID | None = None,
        task_id: uuid.UUID | None = None,
    ) -> None:
        usage = ModelUsage(
            project_id=project_id,
            task_id=task_id,
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
        )
        self.db.add(usage)
        await self.db.flush()

    async def get_dashboard(self, project_id: uuid.UUID | None = None) -> dict[str, Any]:
        """Generate a metrics dashboard."""
        return {
            "runs": await self._run_metrics(project_id),
            "tokens": await self._token_metrics(project_id),
            "deployments": await self._deployment_metrics(project_id),
        }

    async def _run_metrics(self, project_id: uuid.UUID | None) -> dict[str, Any]:
        base = select(
            Run.run_type,
            Run.status,
            func.count(Run.id).label("count"),
        ).group_by(Run.run_type, Run.status)
        if project_id:
            base = base.where(Run.project_id == project_id)
        result = await self.db.execute(base)
        rows = result.all()

        metrics: dict[str, dict[str, int]] = {}
        for run_type, status, count in rows:
            metrics.setdefault(run_type, {})[status] = count

        # Compute success rates
        rates: dict[str, float] = {}
        for rt, statuses in metrics.items():
            total = sum(statuses.values())
            success = statuses.get("success", 0)
            rates[rt] = (success / total * 100) if total > 0 else 0.0

        return {"breakdown": metrics, "success_rates": rates}

    async def _token_metrics(self, project_id: uuid.UUID | None) -> dict[str, Any]:
        base = select(
            ModelUsage.provider,
            func.sum(ModelUsage.input_tokens).label("total_input"),
            func.sum(ModelUsage.output_tokens).label("total_output"),
            func.sum(ModelUsage.cost_usd).label("total_cost"),
            func.avg(ModelUsage.latency_ms).label("avg_latency"),
        ).group_by(ModelUsage.provider)
        if project_id:
            base = base.where(ModelUsage.project_id == project_id)
        result = await self.db.execute(base)
        rows = result.all()

        return {
            row[0]: {
                "input_tokens": int(row[1] or 0),
                "output_tokens": int(row[2] or 0),
                "total_cost_usd": float(row[3] or 0),
                "avg_latency_ms": float(row[4] or 0),
            }
            for row in rows
        }

    async def _deployment_metrics(self, project_id: uuid.UUID | None) -> dict[str, Any]:
        base = select(
            DeploymentHistory.provider,
            DeploymentHistory.status,
            func.count(DeploymentHistory.id).label("count"),
        ).group_by(DeploymentHistory.provider, DeploymentHistory.status)
        if project_id:
            base = base.where(DeploymentHistory.project_id == project_id)
        result = await self.db.execute(base)
        rows = result.all()

        metrics: dict[str, dict[str, int]] = {}
        for provider, status, count in rows:
            metrics.setdefault(provider, {})[status] = count
        return metrics
