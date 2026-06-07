"""Health check endpoint."""

from __future__ import annotations

import traceback

from fastapi import APIRouter
from sqlalchemy import text

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    """Basic liveness probe."""
    return {"status": "healthy", "service": "devbuddy-lite"}


@router.get("/health/db")
async def health_db() -> dict:
    """Deep health check — tests database connectivity."""
    try:
        from app.db.session import engine
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            result.fetchone()
        return {"status": "healthy", "database": "connected"}
    except Exception as exc:
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }
