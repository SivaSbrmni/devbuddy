"""Pydantic schemas for agent sessions."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


SessionStatus = Literal[
    "queued", "planning", "running", "paused", "completed", "failed", "terminated"
]
SessionMode = Literal["ask", "plan", "session"]


class PlanStep(BaseModel):
    id: str
    title: str
    goal: str
    success_criteria: str = ""
    status: Literal["pending", "active", "completed", "failed", "skipped"] = "pending"


class SessionPlan(BaseModel):
    version: int = 1
    summary: str = ""
    steps: list[PlanStep] = Field(default_factory=list)


class SessionCreate(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=32000)
    title: Optional[str] = Field(None, max_length=255)
    mode: SessionMode = "session"
    conversation_id: Optional[uuid.UUID] = None
    repository_owner: Optional[str] = None
    repository_name: Optional[str] = None
    repository_url: Optional[str] = None
    branch: Optional[str] = None


class SessionMessageCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=16000)


class SessionResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    conversation_id: Optional[uuid.UUID]
    title: str
    prompt: str
    mode: str
    status: str
    repository_url: Optional[str]
    repository_owner: Optional[str]
    repository_name: Optional[str]
    branch: Optional[str]
    plan: dict[str, Any]
    current_step_index: int
    step_summaries: list[str]
    devbox_type: str
    devbox_ref: Optional[str]
    github_run_id: Optional[int]
    github_run_url: Optional[str]
    pr_url: Optional[str]
    pr_number: Optional[int]
    result: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]

    model_config = {"from_attributes": True}


class SessionListItem(BaseModel):
    id: uuid.UUID
    title: str
    status: str
    mode: str
    repository_name: Optional[str]
    pr_url: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SessionEventPayload(BaseModel):
    type: str
    session_id: str
    seq: int
    timestamp: int
    payload: dict[str, Any]


class SessionEventRecordResponse(BaseModel):
    id: uuid.UUID
    seq: int
    event_type: str
    payload: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}
