import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import get_current_user
from app.schemas.audit import AuditLogOut
from app.services.audit_service import list_audit_logs
from app.services.task_service import get_or_create_default_tenant

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=list[AuditLogOut])
async def get_audit_logs(
    task_id: Optional[uuid.UUID] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    tenant = await get_or_create_default_tenant(db)
    return await list_audit_logs(db, tenant.id, task_id=task_id, limit=limit, offset=offset)
