import httpx
from datetime import datetime, timedelta
from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger("loki_service")


async def query_loki(
    query: str,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = 100,
) -> list[dict]:
    if not start:
        start = datetime.utcnow() - timedelta(hours=1)
    if not end:
        end = datetime.utcnow()

    params = {
        "query": query,
        "start": str(int(start.timestamp() * 1e9)),
        "end": str(int(end.timestamp() * 1e9)),
        "limit": limit,
        "direction": "backward",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{settings.LOKI_URL}/loki/api/v1/query_range", params=params)
            resp.raise_for_status()
            data = resp.json()
            results = []
            for stream in data.get("data", {}).get("result", []):
                labels = stream.get("stream", {})
                for ts, line in stream.get("values", []):
                    results.append({"timestamp": ts, "labels": labels, "line": line})
            return results
    except Exception as e:
        logger.warning("loki_query_failed", error=str(e), query=query)
        return []


async def get_recent_errors(last_minutes: int = 60) -> list[dict]:
    start = datetime.utcnow() - timedelta(minutes=last_minutes)
    return await query_loki('{service="backend"} |= "ERROR"', start=start, limit=200)


async def get_logs_by_service(service: str, level: str | None = None, last_minutes: int = 60, limit: int = 100) -> list[dict]:
    start = datetime.utcnow() - timedelta(minutes=last_minutes)
    logql = f'{{service="{service}"}}'
    if level:
        logql += f' |= "{level.upper()}"'
    return await query_loki(logql, start=start, limit=limit)


async def get_logs_by_task(task_id: str, last_minutes: int = 1440) -> list[dict]:
    start = datetime.utcnow() - timedelta(minutes=last_minutes)
    return await query_loki(f'{{service="backend"}} |= "{task_id}"', start=start, limit=500)
