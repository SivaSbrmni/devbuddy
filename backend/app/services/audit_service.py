import uuid
import hashlib
import json
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.models.audit import AuditLog
from app.core.logger import get_logger

logger = get_logger("audit_service")


def _compute_signature(data: dict) -> str:
    payload = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


async def create_audit_log(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    task_id: uuid.UUID | None,
    event_type: str,
    actor_type: str,
    actor_id: str,
    action: str,
    outcome: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    details: dict = {},
    trace_id: str | None = None,
    ip_address: str | None = None,
) -> AuditLog:
    data = {
        "tenant_id": str(tenant_id),
        "task_id": str(task_id) if task_id else None,
        "event_type": event_type,
        "actor_id": actor_id,
        "action": action,
        "outcome": outcome,
        "timestamp": datetime.utcnow().isoformat(),
    }
    entry = AuditLog(
        tenant_id=tenant_id,
        task_id=task_id,
        event_type=event_type,
        actor_type=actor_type,
        actor_id=actor_id,
        resource_type=resource_type,
        resource_id=resource_id,
        action=action,
        outcome=outcome,
        details=details,
        trace_id=trace_id,
        ip_address=ip_address,
        signature=_compute_signature(data),
    )
    db.add(entry)
    await db.flush()
    logger.info("audit_log_created", event_type=event_type, actor_id=actor_id, outcome=outcome, task_id=str(task_id) if task_id else None)
    return entry


async def list_audit_logs(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    task_id: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[AuditLog]:
    query = select(AuditLog).where(AuditLog.tenant_id == tenant_id).order_by(desc(AuditLog.created_at)).offset(offset).limit(limit)
    if task_id:
        query = query.where(AuditLog.task_id == task_id)
    result = await db.execute(query)
    return list(result.scalars().all())
