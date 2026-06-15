"""Project and related persistence models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.task import Milestone, Task
    from app.models.execution import Run
    from app.models.memory import ProjectMemory


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    repo_url: Mapped[str | None] = mapped_column(String(512))
    repo_branch: Mapped[str] = mapped_column(String(255), default="main")
    status: Mapped[str] = mapped_column(
        String(20),
        default="active",
    )
    tech_stack: Mapped[dict] = mapped_column(JSONB, default=dict)
    config: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    tasks: Mapped[list[Task]] = relationship("Task", back_populates="project", cascade="all, delete-orphan")
    milestones: Mapped[list[Milestone]] = relationship(
        "Milestone", back_populates="project", cascade="all, delete-orphan"
    )
    runs: Mapped[list[Run]] = relationship("Run", back_populates="project", cascade="all, delete-orphan")
    memories: Mapped[list[ProjectMemory]] = relationship(
        "ProjectMemory", back_populates="project", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_projects_status", "status"),)
