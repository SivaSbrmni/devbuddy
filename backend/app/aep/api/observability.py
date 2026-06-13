"""Observability API — Phase 6.

Metrics endpoint for Prometheus scraping and trace inspection.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.aep.observability import aep_logger
from app.aep.observability_ext.metrics import get_metrics_registry
from app.aep.observability_ext.tracing import get_tracer

router = APIRouter(prefix="/aep/observability", tags=["aep-observability"])
_logger = aep_logger("aep.api.observability")


@router.get("/metrics")
async def get_metrics() -> dict[str, Any]:
    """Return all AEP metrics for dashboard consumption."""
    registry = get_metrics_registry()
    return registry.get_all_metrics()


@router.get("/traces")
async def get_recent_traces(limit: int = 50) -> dict[str, Any]:
    """Return recent trace spans."""
    tracer = get_tracer()
    spans = tracer.get_recent_spans(limit=limit)
    return {"spans": spans, "count": len(spans)}


@router.get("/traces/{trace_id}")
async def get_trace(trace_id: str) -> dict[str, Any]:
    """Return all spans for a specific trace."""
    tracer = get_tracer()
    spans = tracer.get_trace(trace_id)
    return {"trace_id": trace_id, "spans": spans, "count": len(spans)}
