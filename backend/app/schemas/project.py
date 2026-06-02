"""Pydantic schemas for Project CRUD and pipeline requests."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ── Project ──────────────────────────────────────────────────────────
class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = ""
    repo_url: str | None = None
    repo_branch: str = "main"
    tech_stack: dict[str, Any] = {}
    config: dict[str, Any] = {}


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    repo_url: str | None = None
    repo_branch: str | None = None
    status: str | None = None
    tech_stack: dict[str, Any] | None = None
    config: dict[str, Any] | None = None


class ProjectOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    repo_url: str | None
    repo_branch: str
    status: str
    tech_stack: dict[str, Any]
    config: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Pipeline ─────────────────────────────────────────────────────────
class PipelineRequest(BaseModel):
    requirements: str = Field(..., min_length=1)
    tech_stack: dict[str, Any] = {}


class CodingTaskRequest(BaseModel):
    task_description: str = Field(..., min_length=1)
    file_path: str = ""
    existing_code: str = ""


# ── Task ─────────────────────────────────────────────────────────────
class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str = ""
    task_type: str
    milestone_id: uuid.UUID | None = None
    parent_id: uuid.UUID | None = None
    priority: int = 0
    context: dict[str, Any] = {}


class TaskOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    milestone_id: uuid.UUID | None
    parent_id: uuid.UUID | None
    title: str
    description: str
    task_type: str
    status: str
    priority: int
    context: dict[str, Any]
    result: dict[str, Any]
    retry_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Memory ───────────────────────────────────────────────────────────
class MemoryCreate(BaseModel):
    category: str
    title: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    metadata: dict[str, Any] = {}


class MemoryOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    category: str
    title: str
    content: str
    metadata_: dict[str, Any] = Field(alias="metadata_")
    created_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}


# ── Knowledge ────────────────────────────────────────────────────────
class KnowledgeCreate(BaseModel):
    category: str
    title: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    tags: list[str] = []
    project_id: uuid.UUID | None = None


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    limit: int = 5
    category: str | None = None
    project_id: uuid.UUID | None = None


class KnowledgeOut(BaseModel):
    id: str
    category: str
    title: str
    content: str
    tags: list[str] | dict[str, Any]
    distance: float | None = None
    usage_count: int

    model_config = {"from_attributes": True}


# ── Skill ────────────────────────────────────────────────────────────
class SkillOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    category: str
    steps: dict[str, Any] | list[Any]
    usage_count: int
    success_rate: float | None

    model_config = {"from_attributes": True}


# ── Run / Execution ─────────────────────────────────────────────────
class RunOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    task_id: uuid.UUID | None
    run_type: str
    status: str
    trigger: str
    result: dict[str, Any]
    retry_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Deployment ───────────────────────────────────────────────────────
class DeployRequest(BaseModel):
    provider: str = Field(..., pattern=r"^(railway|vercel|docker)$")
    config: dict[str, Any] = {}
    environment: str = "production"
    version: str = ""


# ── Dashboard / Metrics ─────────────────────────────────────────────
class DashboardOut(BaseModel):
    runs: dict[str, Any]
    tokens: dict[str, Any]
    deployments: dict[str, Any]
