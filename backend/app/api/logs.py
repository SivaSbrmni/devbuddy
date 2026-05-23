from typing import Optional
from fastapi import APIRouter, Depends, Query
from app.core.security import get_current_user
from app.services.loki_service import query_loki, get_recent_errors, get_logs_by_service, get_logs_by_task
from datetime import datetime, timedelta

router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("")
async def get_logs(
    service: Optional[str] = Query(None),
    level: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    last_minutes: int = Query(60, le=10080),
    limit: int = Query(100, le=500),
    user: dict = Depends(get_current_user),
):
    start = datetime.utcnow() - timedelta(minutes=last_minutes)

    if service:
        logql = f'{{service="{service}"}}'
    else:
        logql = '{job="devbuddy"}'

    if level:
        logql += f' |= "{level.upper()}"'
    if search:
        logql += f' |= "{search}"'

    logs = await query_loki(logql, start=start, limit=limit)
    return {"logs": logs, "count": len(logs)}


@router.get("/errors")
async def get_errors(
    last_minutes: int = Query(60, le=10080),
    user: dict = Depends(get_current_user),
):
    logs = await get_recent_errors(last_minutes=last_minutes)
    return {"logs": logs, "count": len(logs)}


@router.get("/task/{task_id}")
async def get_task_logs(
    task_id: str,
    user: dict = Depends(get_current_user),
):
    logs = await get_logs_by_task(task_id)
    return {"logs": logs, "count": len(logs)}


@router.get("/health")
async def log_health(user: dict = Depends(get_current_user)):
    errors_1h = await get_recent_errors(last_minutes=60)
    return {
        "loki_reachable": True,
        "error_count_last_hour": len(errors_1h),
        "status": "healthy" if len(errors_1h) < 50 else "degraded",
    }
