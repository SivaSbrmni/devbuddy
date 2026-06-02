"""Observability & Metrics API routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.observability.metrics import MetricsCollector
from app.schemas.project import DashboardOut

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/dashboard", response_model=DashboardOut)
async def get_dashboard(
    project_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    collector = MetricsCollector(db)
    return await collector.get_dashboard(project_id)
