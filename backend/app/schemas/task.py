from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime
import uuid
from app.models.task import TaskState


class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    repo_id: Optional[str] = None
    branch: Optional[str] = None
    policy_profile: str = "standard"
    metadata: dict = {}


class TaskStateTransition(BaseModel):
    to_state: TaskState
    reason: Optional[str] = None
    payload: dict = {}


class TaskEventOut(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    event_type: str
    from_state: Optional[str]
    to_state: Optional[str]
    actor_type: str
    actor_id: Optional[str]
    payload: dict
    created_at: datetime

    class Config:
        from_attributes = True


class TaskOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    title: str
    description: Optional[str]
    repo_id: Optional[str]
    branch: Optional[str]
    state: TaskState
    policy_profile: str
    iteration_count: int
    token_budget_used: int
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]
    events: list[TaskEventOut] = []

    class Config:
        from_attributes = True


class TaskListOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    title: str
    state: TaskState
    repo_id: Optional[str]
    branch: Optional[str]
    iteration_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WebSocketEvent(BaseModel):
    type: str = "TASK_EVENT"
    task_id: str
    timestamp: str
    event: dict[str, Any]
