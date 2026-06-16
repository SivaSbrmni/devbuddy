"""Conversation, Message, and ConversationTask models - server-side persistence."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class Conversation(Base):
    """Permanent, server-side conversation that survives everything."""
    
    __tablename__ = "conversations"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    
    # Basic info
    title: Mapped[str] = mapped_column(String(255), default="New conversation")
    
    # Repository context
    repository_url: Mapped[str | None] = mapped_column(String(512))
    repository_name: Mapped[str | None] = mapped_column(String(255))
    repository_owner: Mapped[str | None] = mapped_column(String(255))
    branch: Mapped[str | None] = mapped_column(String(255))
    
    # Working state (auto-updated after each task)
    summary: Mapped[str] = mapped_column(Text, default="")  # "Implementing JWT auth..."
    current_goal: Mapped[str] = mapped_column(Text, default="")
    completed_tasks: Mapped[list] = mapped_column(JSONB, default=list)  # [{task_id, title, commit, pr}]
    open_tasks: Mapped[list] = mapped_column(JSONB, default=list)
    modified_files: Mapped[list] = mapped_column(JSONB, default=list)  # All files across convo
    important_decisions: Mapped[list] = mapped_column(JSONB, default=list)
    
    # Status
    status: Mapped[str] = mapped_column(String(20), default="active")  # active, archived, completed
    
    # Sync
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(default=0)  # For optimistic locking
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    
    # Relationships
    user: Mapped[User] = relationship("User", back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(
        "Message", back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at"
    )
    tasks: Mapped[list["ConversationTask"]] = relationship(
        "ConversationTask", back_populates="conversation", cascade="all, delete-orphan"
    )
    events: Mapped[list["ConversationEvent"]] = relationship(
        "ConversationEvent", back_populates="conversation", cascade="all, delete-orphan"
    )
    
    __table_args__ = (
        Index("ix_conversations_user_id", "user_id"),
        Index("ix_conversations_status", "user_id", "status"),
        Index("ix_conversations_repo", "repository_url"),
        Index("ix_conversations_last_message", "user_id", "last_message_at"),
    )


class Message(Base):
    """Every message stored server-side with full metadata."""
    
    __tablename__ = "messages"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False
    )
    
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user, assistant, system
    content: Mapped[str] = mapped_column(Text, default="")
    
    # Rich metadata for agent context
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    # {
    #   task_id: "...",
    #   run_id: "...",
    #   tool_calls: [...],
    #   files: [{name, path, content_hash}],
    #   steps: [...],
    #   task_card: {...},  # For UI reconstruction
    # }
    
    # Streaming state (for long responses)
    is_complete: Mapped[bool] = mapped_column(default=True)
    chunks_received: Mapped[int] = mapped_column(default=1)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    conversation: Mapped[Conversation] = relationship("Conversation", back_populates="messages")
    
    __table_args__ = (
        Index("ix_messages_conversation_id", "conversation_id"),
        Index("ix_messages_created", "conversation_id", "created_at"),
    )


class ConversationTask(Base):
    """One conversation has many tasks - the core execution unit."""
    
    __tablename__ = "conversation_tasks"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False
    )
    
    # Hierarchy
    parent_task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversation_tasks.id")
    )
    previous_task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversation_tasks.id")
    )
    
    # Task info
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, running, completed, error
    
    # Git context
    branch: Mapped[str] = mapped_column(String(255), nullable=False)
    commit_hash: Mapped[str | None] = mapped_column(String(40))
    pr_url: Mapped[str | None] = mapped_column(String(512))
    pr_number: Mapped[int | None] = mapped_column()
    
    # Artifacts
    modified_files: Mapped[list] = mapped_column(JSONB, default=list)
    created_artifacts: Mapped[list] = mapped_column(JSONB, default=list)
    
    # Result summary
    result: Mapped[dict] = mapped_column(JSONB, default=dict)
    # {
    #   summary: "Implemented JWT with refresh tokens",
    #   files_changed: [...],
    #   tests_passed: true,
    #   reasoning_summary: "...",
    # }
    
    # Timings
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    conversation: Mapped[Conversation] = relationship("Conversation", back_populates="tasks")
    events: Mapped[list["TaskEvent"]] = relationship(
        "TaskEvent", back_populates="task", cascade="all, delete-orphan"
    )
    
    __table_args__ = (
        Index("ix_tasks_conversation_id", "conversation_id"),
        Index("ix_tasks_status", "conversation_id", "status"),
        Index("ix_tasks_branch", "branch"),
    )


class ConversationEvent(Base):
    """Event sourcing - immutable log of everything that happened."""
    
    __tablename__ = "conversation_events"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False
    )
    
    # Event classification
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # message_created, task_started, planner_finished, files_read, files_modified,
    # tests_started, tests_passed, commit_created, pr_opened, agent_thinking, etc.
    
    # Actor
    actor: Mapped[str] = mapped_column(String(20), default="system")  # user, agent, system
    
    # Payload (event-specific data)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    
    # Previous state (for rollback/debug)
    previous_state: Mapped[dict | None] = mapped_column(JSONB)
    
    # Ordering
    sequence_number: Mapped[int] = mapped_column()  # Monotonic within conversation
    vector_clock: Mapped[str] = mapped_column(String(100), default="")  # For distributed ordering
    
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    duration_ms: Mapped[int | None] = mapped_column()
    
    # Relationships
    conversation: Mapped[Conversation] = relationship("Conversation", back_populates="events")
    
    __table_args__ = (
        Index("ix_events_conversation_id", "conversation_id"),
        Index("ix_events_sequence", "conversation_id", "sequence_number"),
        Index("ix_events_type", "event_type"),
    )


class TaskEvent(Base):
    """Granular events within a task execution."""
    
    __tablename__ = "task_events"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversation_tasks.id"), nullable=False
    )
    
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # agent_step, tool_call, llm_request, file_read, file_write, 
    # command_exec, test_run, git_commit, pr_create, etc.
    
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    # {
    #   step_name: "analyze_code",
    #   tool: "read_file",
    #   input: {path: "src/main.py"},
    #   output: {...},
    #   error: null,
    # }
    
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    duration_ms: Mapped[int | None] = mapped_column()
    
    # Relationships
    task: Mapped[ConversationTask] = relationship("ConversationTask", back_populates="events")
    
    __table_args__ = (
        Index("ix_task_events_task_id", "task_id"),
        Index("ix_task_events_type", "event_type"),
    )
