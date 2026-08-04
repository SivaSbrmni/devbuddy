"""Agent session models — Devin-style session-centric execution."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.conversation import Conversation


class AgentSession(Base):
    """A single autonomous engineering session (Devin session equivalent)."""

    __tablename__ = "agent_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=True
    )

    title: Mapped[str] = mapped_column(String(255), default="New session")
    prompt: Mapped[str] = mapped_column(Text, default="")
    mode: Mapped[str] = mapped_column(String(20), default="session")  # ask | plan | session

    status: Mapped[str] = mapped_column(
        String(20), default="queued"
    )  # queued | planning | running | paused | completed | failed | terminated

    repository_url: Mapped[str | None] = mapped_column(String(512))
    repository_owner: Mapped[str | None] = mapped_column(String(255))
    repository_name: Mapped[str | None] = mapped_column(String(255))
    branch: Mapped[str | None] = mapped_column(String(255))

    plan: Mapped[dict] = mapped_column(JSONB, default=dict)
    current_step_index: Mapped[int] = mapped_column(Integer, default=0)
    step_summaries: Mapped[list] = mapped_column(JSONB, default=list)

    devbox_type: Mapped[str] = mapped_column(String(32), default="github_actions")
    devbox_ref: Mapped[str | None] = mapped_column(String(255))
    github_run_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    github_run_url: Mapped[str | None] = mapped_column(String(512))

    pr_url: Mapped[str | None] = mapped_column(String(512))
    pr_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result: Mapped[dict] = mapped_column(JSONB, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="agent_sessions")
    conversation: Mapped["Conversation | None"] = relationship("Conversation")
    events: Mapped[list["SessionEventRecord"]] = relationship(
        "SessionEventRecord",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="SessionEventRecord.seq",
    )

    __table_args__ = (
        Index("ix_agent_sessions_user_id", "user_id"),
        Index("ix_agent_sessions_status", "user_id", "status"),
        Index("ix_agent_sessions_conversation", "conversation_id"),
    )


class SessionEventRecord(Base):
    """Persisted session events for replay and WebSocket catch-up."""

    __tablename__ = "session_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_sessions.id", ondelete="CASCADE"), nullable=False
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped["AgentSession"] = relationship("AgentSession", back_populates="events")

    __table_args__ = (
        Index("ix_session_events_session_seq", "session_id", "seq"),
    )
