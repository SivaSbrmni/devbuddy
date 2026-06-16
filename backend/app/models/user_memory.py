"""UserMemory and RepositoryMemory - persistent preferences and repository knowledge."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    pass


class UserMemory(Base):
    """Personal preferences that follow the user across devices and conversations."""
    
    __tablename__ = "user_memories"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True
    )
    
    # ─── Coding Preferences ─────────────────────────────────────────────
    preferred_language: Mapped[str] = mapped_column(String(50), default="")
    preferred_framework: Mapped[str] = mapped_column(String(50), default="")
    coding_style: Mapped[str] = mapped_column(
        String(20), default=""
    )  # functional, oop, mixed, procedural
    
    # ─── Style Preferences ──────────────────────────────────────────────
    commit_style: Mapped[str] = mapped_column(
        String(20), default="conventional"
    )  # conventional, semantic, simple, detailed
    pr_style: Mapped[str] = mapped_column(
        String(20), default="detailed"
    )  # detailed, minimal, technical, business
    testing_preference: Mapped[str] = mapped_column(
        String(20), default="always"
    )  # always, critical_only, on_request, none
    documentation_style: Mapped[str] = mapped_column(
        String(20), default="inline"
    )  # inline, markdown, comprehensive, minimal
    
    # ─── Response Preferences ───────────────────────────────────────────
    response_style: Mapped[str] = mapped_column(
        String(20), default="detailed"
    )  # concise, detailed, tutorial, socratic
    explanation_depth: Mapped[str] = mapped_column(
        String(20), default="balanced"
    )  # high_level, balanced, deep_dive
    
    # ─── Architecture Preferences ───────────────────────────────────────
    preferred_architecture: Mapped[str] = mapped_column(
        String(50), default=""
    )  # hexagonal, clean, mvc, microservices, monolith
    state_management: Mapped[str] = mapped_column(String(50), default="")
    dependency_injection: Mapped[bool] = mapped_column(default=True)
    
    # ─── Favorites & History ──────────────────────────────────────────
    favorite_repositories: Mapped[list] = mapped_column(JSONB, default=list)  # [repo_urls]
    recent_repositories: Mapped[list] = mapped_column(JSONB, default=list)  # [{url, last_used}]
    favorite_models: Mapped[list] = mapped_column(JSONB, default=list)  # [provider_id]
    
    # ─── Pinned Content ───────────────────────────────────────────────
    pinned_conversations: Mapped[list] = mapped_column(JSONB, default=list)  # [conversation_ids]
    
    # ─── Custom Instructions ──────────────────────────────────────────
    custom_instructions: Mapped[str] = mapped_column(
        Text, 
        default=""
    )  # Free text: "Always use Java 21", "Never use var", etc.
    
    # ─── Patterns Learned ─────────────────────────────────────────────
    frequent_prompts: Mapped[list] = mapped_column(
        JSONB, 
        default=list
    )  # [{prompt, count, last_used, category}]
    
    # ─── IDE Preferences ──────────────────────────────────────────────
    preferred_editor: Mapped[str] = mapped_column(String(50), default="")
    theme_preference: Mapped[str] = mapped_column(String(20), default="dark")
    
    # ─── Notification Preferences ─────────────────────────────────────
    notify_on_completion: Mapped[bool] = mapped_column(default=True)
    notify_on_error: Mapped[bool] = mapped_column(default=True)
    email_digest: Mapped[str] = mapped_column(String(20), default="weekly")  # daily, weekly, never
    
    # ─── Usage Stats ─────────────────────────────────────────────────
    total_conversations: Mapped[int] = mapped_column(default=0)
    total_tasks_completed: Mapped[int] = mapped_column(default=0)
    total_lines_written: Mapped[int] = mapped_column(default=0)
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    
    __table_args__ = (
        Index("ix_user_memories_user_id", "user_id"),
    )


class RepositoryMemory(Base):
    """Per-repository knowledge that persists across conversations."""
    
    __tablename__ = "repository_memories"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Repository identity
    repo_url: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    repo_name: Mapped[str] = mapped_column(String(255), default="")
    repo_owner: Mapped[str] = mapped_column(String(255), default="")
    
    # ─── Architecture ─────────────────────────────────────────────────
    tech_stack: Mapped[dict] = mapped_column(
        JSONB, 
        default=dict
    )  # {languages: [...], frameworks: [...], patterns: [...]}
    
    folder_structure: Mapped[dict] = mapped_column(
        JSONB, 
        default=dict
    )  # Cached tree with descriptions
    
    business_rules: Mapped[list] = mapped_column(
        JSONB, 
        default=list
    )  # Extracted business logic
    
    # ─── Standards ─────────────────────────────────────────────────────
    coding_standards: Mapped[str] = mapped_column(
        Text, 
        default=""
    )  # Inferred from codebase
    testing_patterns: Mapped[str] = mapped_column(Text, default="")
    architecture_decisions: Mapped[list] = mapped_column(
        JSONB, 
        default=list
    )  # ADRs extracted from code/docs
    
    # ─── History ──────────────────────────────────────────────────────
    previous_prs: Mapped[list] = mapped_column(
        JSONB, 
        default=list
    )  # [{number, title, summary, author}]
    
    recent_changes: Mapped[list] = mapped_column(
        JSONB, 
        default=list
    )  # [{commit, message, files, date}]
    
    known_issues: Mapped[list] = mapped_column(
        JSONB, 
        default=list
    )  # [{title, status, workarounds}]
    
    common_libraries: Mapped[list] = mapped_column(JSONB, default=list)
    
    # ─── Relationships ────────────────────────────────────────────────
    related_repositories: Mapped[list] = mapped_column(
        JSONB, 
        default=list
    )  # [repo_urls] - microservices in same org
    
    # ─── Conversations that touched this repo ─────────────────────────
    conversation_count: Mapped[int] = mapped_column(default=0)
    last_conversation_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    
    # ─── Auto-extracted insights ──────────────────────────────────────
    key_files: Mapped[list] = mapped_column(
        JSONB, 
        default=list
    )  # [{path, description, importance}]
    
    entry_points: Mapped[list] = mapped_column(
        JSONB, 
        default=list
    )  # Main files for different features
    
    database_schema: Mapped[dict] = mapped_column(
        JSONB, 
        default=dict
    )  # If DB models found
    
    api_endpoints: Mapped[list] = mapped_column(
        JSONB, 
        default=list
    )  # If backend detected
    
    # ─── Sync tracking ───────────────────────────────────────────────
    last_analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    analysis_version: Mapped[str] = mapped_column(String(20), default="")
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    
    __table_args__ = (
        Index("ix_repo_memories_url", "repo_url"),
        Index("ix_repo_memories_owner", "repo_owner"),
    )


class OrganizationMemory(Base):
    """Organization-wide standards and knowledge."""
    
    __tablename__ = "organization_memories"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    
    category: Mapped[str] = mapped_column(
        String(50), 
        nullable=False
    )  # coding_standards, security_policy, deployment_rules, compliance
    
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Applies to
    applies_to_repos: Mapped[list] = mapped_column(JSONB, default=list)  # [repo_urls or "*"]
    applies_to_languages: Mapped[list] = mapped_column(JSONB, default=list)
    applies_to_frameworks: Mapped[list] = mapped_column(JSONB, default=list)
    
    # Enforcement
    is_required: Mapped[bool] = mapped_column(default=False)
    enforcement_level: Mapped[str] = mapped_column(
        String(20), default="suggest"
    )  # suggest, warn, enforce, block
    
    # Metadata
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    updated_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    
    __table_args__ = (
        Index("ix_org_memories_org_id", "org_id"),
        Index("ix_org_memories_category", "org_id", "category"),
    )
