from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid


class AuditLogOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    task_id: Optional[uuid.UUID]
    event_type: str
    actor_type: str
    actor_id: str
    resource_type: Optional[str]
    resource_id: Optional[str]
    action: str
    outcome: str
    details: dict
    trace_id: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
