"""
DevBuddy Enterprise Agent Platform - MCP Server
Exposes platform logs and audit data as AI-queryable tools via Loki + backend API.
"""
import os
import json
from datetime import datetime, timedelta, timezone

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

LOKI_URL = os.getenv("LOKI_URL", "http://localhost:3100")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
API_TOKEN = os.getenv("MCP_API_TOKEN", "")

mcp = FastMCP("DevBuddy Agent Platform")


def _auth_headers() -> dict:
    if API_TOKEN:
        return {"Authorization": f"Bearer {API_TOKEN}"}
    return {}


def _ns_now() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1e9)


def _ns_ago(minutes: int) -> int:
    dt = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    return int(dt.timestamp() * 1e9)


async def _loki_query(logql: str, start_ns: int, end_ns: int, limit: int = 100) -> list[dict]:
    params = {
        "query": logql,
        "start": str(start_ns),
        "end": str(end_ns),
        "limit": str(limit),
        "direction": "backward",
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{LOKI_URL}/loki/api/v1/query_range", params=params)
        resp.raise_for_status()
        data = resp.json()

    results = []
    for stream in data.get("data", {}).get("result", []):
        labels = stream.get("stream", {})
        for ts, line in stream.get("values", []):
            results.append({"timestamp": ts, "labels": labels, "line": line})
    return results


@mcp.tool()
async def query_logs(
    logql: str = '{service="backend"}',
    last_minutes: int = 60,
    limit: int = 50,
) -> str:
    """
    Query platform logs from Loki using LogQL syntax.
    
    Examples:
      - All backend logs: {service="backend"}
      - Error logs: {service="backend"} |= "ERROR"
      - Specific task: {service="backend"} |= "task_id=<uuid>"
    """
    try:
        logs = await _loki_query(logql, _ns_ago(last_minutes), _ns_now(), limit)
        if not logs:
            return "No logs found for the given query."
        lines = []
        for log in logs:
            ts = datetime.fromtimestamp(int(log["timestamp"]) / 1e9, tz=timezone.utc).isoformat()
            try:
                obj = json.loads(log["line"])
                msg = obj.get("event") or obj.get("message") or log["line"]
                level = obj.get("level", "")
                lines.append(f"[{ts}] [{level.upper()}] {msg}")
            except Exception:
                lines.append(f"[{ts}] {log['line']}")
        return "\n".join(lines[:limit])
    except Exception as e:
        return f"Error querying logs: {e}"


@mcp.tool()
async def get_recent_errors(last_minutes: int = 60, limit: int = 20) -> str:
    """
    Get recent ERROR and CRITICAL level log entries from the platform.
    Returns the most recent errors across all services.
    """
    try:
        logql = '{service=~".+"} |= "ERROR"'
        logs = await _loki_query(logql, _ns_ago(last_minutes), _ns_now(), limit)
        if not logs:
            return f"No errors in the last {last_minutes} minutes."
        lines = [f"Found {len(logs)} error(s) in the last {last_minutes} minutes:\n"]
        for log in logs:
            ts = datetime.fromtimestamp(int(log["timestamp"]) / 1e9, tz=timezone.utc).isoformat()
            svc = log["labels"].get("service", "unknown")
            try:
                obj = json.loads(log["line"])
                msg = obj.get("event") or obj.get("message") or log["line"]
                exc = obj.get("exception", "")
                lines.append(f"[{ts}] [{svc}] {msg}{' | ' + exc if exc else ''}")
            except Exception:
                lines.append(f"[{ts}] [{svc}] {log['line']}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error fetching errors: {e}"


@mcp.tool()
async def get_audit_trail(limit: int = 50, event_type: str = "") -> str:
    """
    Get the immutable audit trail from the platform.
    Optionally filter by event_type (e.g. TASK_CREATED, STATE_TRANSITION, USER_LOGIN).
    """
    try:
        url = f"{BACKEND_URL}/api/v1/audit"
        params: dict = {"limit": limit}
        if event_type:
            params["event_type"] = event_type
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, params=params, headers=_auth_headers())
            resp.raise_for_status()
            data = resp.json()

        if not data:
            return "No audit entries found."
        lines = [f"Audit trail ({len(data)} entries):\n"]
        for entry in data:
            ts = entry.get("created_at", "")
            etype = entry.get("event_type", "")
            actor = f"{entry.get('actor_type','?')}:{entry.get('actor_id','?')[:8]}"
            action = entry.get("action", "")
            outcome = entry.get("outcome", "")
            lines.append(f"[{ts}] {etype} | {actor} | {action} | outcome={outcome}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error fetching audit trail: {e}"


@mcp.tool()
async def get_task_execution_log(task_id: str, last_minutes: int = 120) -> str:
    """
    Get all logs and events for a specific task by its UUID.
    Combines structured logs from Loki and task events from the API.
    """
    try:
        logql = f'{{service="backend"}} |= "{task_id}"'
        logs = await _loki_query(logql, _ns_ago(last_minutes), _ns_now(), 200)

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{BACKEND_URL}/api/v1/tasks/{task_id}",
                headers=_auth_headers()
            )
            task = resp.json() if resp.status_code == 200 else {}

        lines = [f"=== Task Execution Log: {task_id} ===\n"]

        if task:
            lines.append(f"Title: {task.get('title', 'N/A')}")
            lines.append(f"State: {task.get('state', 'N/A')}")
            lines.append(f"Iterations: {task.get('iteration_count', 0)}")
            lines.append(f"Policy: {task.get('policy_profile', 'N/A')}\n")

            events = task.get("events", [])
            if events:
                lines.append("--- State Transitions ---")
                for ev in events:
                    lines.append(f"  [{ev.get('created_at','')}] {ev.get('from_state','')} → {ev.get('to_state','')} ({ev.get('event_type','')})")

        if logs:
            lines.append(f"\n--- Application Logs ({len(logs)} entries) ---")
            for log in logs:
                ts = datetime.fromtimestamp(int(log["timestamp"]) / 1e9, tz=timezone.utc).isoformat()
                try:
                    obj = json.loads(log["line"])
                    msg = obj.get("event") or obj.get("message") or log["line"]
                    level = obj.get("level", "info")
                    lines.append(f"  [{ts}] [{level.upper()}] {msg}")
                except Exception:
                    lines.append(f"  [{ts}] {log['line']}")
        else:
            lines.append("\nNo application logs found in Loki for this task.")

        return "\n".join(lines)
    except Exception as e:
        return f"Error fetching task log: {e}"


@mcp.tool()
async def platform_health_summary() -> str:
    """
    Get a comprehensive health summary of the DevBuddy platform.
    Checks API health, recent error rates, and active task counts.
    """
    summary: list[str] = ["=== DevBuddy Platform Health Summary ===\n"]

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{BACKEND_URL}/health")
            api_status = "✅ Healthy" if r.status_code == 200 else f"❌ {r.status_code}"
    except Exception as e:
        api_status = f"❌ Unreachable ({e})"
    summary.append(f"API Status: {api_status}")

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{LOKI_URL}/ready")
            loki_status = "✅ Ready" if r.status_code == 200 else f"⚠️ {r.status_code}"
    except Exception as e:
        loki_status = f"❌ Unreachable ({e})"
    summary.append(f"Loki Status: {loki_status}")

    try:
        error_logs = await _loki_query('{service=~".+"} |= "ERROR"', _ns_ago(60), _ns_now(), 500)
        summary.append(f"Errors (last 1h): {len(error_logs)}")
        if len(error_logs) > 20:
            summary.append("  ⚠️  High error rate detected!")
    except Exception as e:
        summary.append(f"Error count: unavailable ({e})")

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{BACKEND_URL}/api/v1/tasks", headers=_auth_headers())
            if r.status_code == 200:
                tasks = r.json()
                active = [t for t in tasks if t["state"] not in ("COMPLETED", "FAILED", "QUARANTINED")]
                summary.append(f"Total tasks: {len(tasks)}")
                summary.append(f"Active tasks: {len(active)}")
            else:
                summary.append("Tasks: auth required")
    except Exception as e:
        summary.append(f"Tasks: unavailable ({e})")

    summary.append(f"\nTimestamp: {datetime.now(timezone.utc).isoformat()}")
    return "\n".join(summary)


if __name__ == "__main__":
    mcp.run(transport="stdio")
