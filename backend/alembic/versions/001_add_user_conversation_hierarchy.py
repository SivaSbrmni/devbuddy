"""Add User, Conversation, and LLM Provider hierarchy.

Revision ID: 001
Revises:
Create Date: 2026-06-16

This migration creates the foundation for:
- Multi-tenant organizations
- Server-side persistent conversations
- Universal LLM provider architecture
- 5-layer memory hierarchy
- Event sourcing foundation
"""

from __future__ import annotations

import uuid
from typing import Sequence

from alembic import op
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text, Boolean, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers
revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create all new tables for cloud-native architecture."""

    # ─── Organizations ─────────────────────────────────────────────────
    op.create_table(
        "organizations",
        Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        Column("name", String(255), nullable=False),
        Column("slug", String(100), nullable=False, unique=True),
        Column("plan", String(20), default="free"),
        Column("settings", JSONB, default=dict),
        Column("created_at", DateTime(timezone=True), server_default=func.now()),
        Column("updated_at", DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
    )

    # ─── Users ─────────────────────────────────────────────────────────
    op.create_table(
        "users",
        Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        Column("email", String(255), nullable=False, unique=True),
        Column("name", String(255), default=""),
        Column("avatar_url", String(512), default=""),
        Column("org_id", UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False),
        Column("preferences", JSONB, default=dict),
        Column("is_active", Boolean, default=True),
        Column("last_login_at", DateTime(timezone=True), nullable=True),
        Column("created_at", DateTime(timezone=True), server_default=func.now()),
        Column("updated_at", DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_org_id", "users", ["org_id"])

    # ─── User Sessions ─────────────────────────────────────────────────
    op.create_table(
        "user_sessions",
        Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        Column("user_id", UUID(as_uuid=True), ForeignKey("users.id"), nullable=False),
        Column("device_type", String(20), default="unknown"),
        Column("device_name", String(100), default=""),
        Column("browser", String(50), default=""),
        Column("ip_address", String(45), default=""),
        Column("websocket_channel", String(100), default=""),
        Column("is_active", Boolean, default=True),
        Column("last_active_at", DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
        Column("created_at", DateTime(timezone=True), server_default=func.now()),
    )
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])
    op.create_index("ix_user_sessions_active", "user_sessions", ["user_id", "is_active"])

    # ─── Conversations ─────────────────────────────────────────────────
    op.create_table(
        "conversations",
        Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        Column("user_id", UUID(as_uuid=True), ForeignKey("users.id"), nullable=False),
        Column("title", String(255), default="New conversation"),
        Column("repository_url", String(512), nullable=True),
        Column("repository_name", String(255), nullable=True),
        Column("repository_owner", String(255), nullable=True),
        Column("branch", String(255), nullable=True),
        Column("summary", Text, default=""),
        Column("current_goal", Text, default=""),
        Column("completed_tasks", JSONB, default=list),
        Column("open_tasks", JSONB, default=list),
        Column("modified_files", JSONB, default=list),
        Column("important_decisions", JSONB, default=list),
        Column("status", String(20), default="active"),
        Column("last_message_at", DateTime(timezone=True), nullable=True),
        Column("version", Integer, default=0),
        Column("created_at", DateTime(timezone=True), server_default=func.now()),
        Column("updated_at", DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
    )
    op.create_index("ix_conversations_user_id", "conversations", ["user_id"])
    op.create_index("ix_conversations_status", "conversations", ["user_id", "status"])
    op.create_index("ix_conversations_repo", "conversations", ["repository_url"])
    op.create_index("ix_conversations_last_message", "conversations", ["user_id", "last_message_at"])

    # ─── Messages ──────────────────────────────────────────────────────
    op.create_table(
        "messages",
        Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        Column("conversation_id", UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False),
        Column("role", String(20), nullable=False),
        Column("content", Text, default=""),
        Column("metadata", JSONB, default=dict),
        Column("is_complete", Boolean, default=True),
        Column("chunks_received", Integer, default=1),
        Column("created_at", DateTime(timezone=True), server_default=func.now()),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])
    op.create_index("ix_messages_created", "messages", ["conversation_id", "created_at"])

    # ─── Conversation Tasks ─────────────────────────────────────────────
    op.create_table(
        "conversation_tasks",
        Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        Column("conversation_id", UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False),
        Column("parent_task_id", UUID(as_uuid=True), ForeignKey("conversation_tasks.id"), nullable=True),
        Column("previous_task_id", UUID(as_uuid=True), ForeignKey("conversation_tasks.id"), nullable=True),
        Column("title", String(255), nullable=False),
        Column("description", Text, default=""),
        Column("status", String(20), default="pending"),
        Column("branch", String(255), nullable=False),
        Column("commit_hash", String(40), nullable=True),
        Column("pr_url", String(512), nullable=True),
        Column("pr_number", Integer, nullable=True),
        Column("modified_files", JSONB, default=list),
        Column("created_artifacts", JSONB, default=list),
        Column("result", JSONB, default=dict),
        Column("started_at", DateTime(timezone=True), nullable=True),
        Column("completed_at", DateTime(timezone=True), nullable=True),
        Column("created_at", DateTime(timezone=True), server_default=func.now()),
    )
    op.create_index("ix_tasks_conversation_id", "conversation_tasks", ["conversation_id"])
    op.create_index("ix_tasks_status", "conversation_tasks", ["conversation_id", "status"])
    op.create_index("ix_tasks_branch", "conversation_tasks", ["branch"])

    # ─── Conversation Events ────────────────────────────────────────────
    op.create_table(
        "conversation_events",
        Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        Column("conversation_id", UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False),
        Column("event_type", String(50), nullable=False),
        Column("actor", String(20), default="system"),
        Column("payload", JSONB, default=dict),
        Column("previous_state", JSONB, nullable=True),
        Column("sequence_number", Integer, nullable=False),
        Column("vector_clock", String(100), default=""),
        Column("timestamp", DateTime(timezone=True), server_default=func.now()),
        Column("duration_ms", Integer, nullable=True),
    )
    op.create_index("ix_events_conversation_id", "conversation_events", ["conversation_id"])
    op.create_index("ix_events_sequence", "conversation_events", ["conversation_id", "sequence_number"])
    op.create_index("ix_events_type", "conversation_events", ["event_type"])

    # ─── Task Events ────────────────────────────────────────────────────
    op.create_table(
        "task_events",
        Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        Column("task_id", UUID(as_uuid=True), ForeignKey("conversation_tasks.id"), nullable=False),
        Column("event_type", String(50), nullable=False),
        Column("payload", JSONB, default=dict),
        Column("timestamp", DateTime(timezone=True), server_default=func.now()),
        Column("duration_ms", Integer, nullable=True),
    )
    op.create_index("ix_task_events_task_id", "task_events", ["task_id"])
    op.create_index("ix_task_events_type", "task_events", ["event_type"])

    # ─── User LLM Providers ───────────────────────────────────────────
    op.create_table(
        "user_llm_providers",
        Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        Column("user_id", UUID(as_uuid=True), ForeignKey("users.id"), nullable=False),
        Column("name", String(100), nullable=False),
        Column("provider_type", String(30), default="openai-compatible"),
        Column("base_url", String(512), nullable=False),
        Column("api_key_encrypted", Text, nullable=False),
        Column("headers", JSONB, default=dict),
        Column("default_model", String(100), nullable=False),
        Column("available_models", JSONB, default=list),
        Column("supports_streaming", Boolean, default=True),
        Column("supports_tools", Boolean, default=True),
        Column("supports_vision", Boolean, default=False),
        Column("context_size", Integer, default=8192),
        Column("max_tokens", Integer, default=4096),
        Column("cost_per_1k_input", Float, default=0.0),
        Column("cost_per_1k_output", Float, default=0.0),
        Column("priority", Integer, default=100),
        Column("is_active", Boolean, default=True),
        Column("is_default", Boolean, default=False),
        Column("last_tested_at", DateTime(timezone=True), nullable=True),
        Column("health_status", String(20), default="unknown"),
        Column("health_message", String(255), default=""),
        Column("latency_ms", Integer, nullable=True),
        Column("request_count", Integer, default=0),
        Column("token_count", Integer, default=0),
        Column("last_used_at", DateTime(timezone=True), nullable=True),
        Column("created_at", DateTime(timezone=True), server_default=func.now()),
        Column("updated_at", DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
    )
    op.create_index("ix_llm_providers_user_id", "user_llm_providers", ["user_id"])
    op.create_index("ix_llm_providers_active", "user_llm_providers", ["user_id", "is_active"])
    op.create_index("ix_llm_providers_default", "user_llm_providers", ["user_id", "is_default"])

    # ─── Provider Routing Rules ────────────────────────────────────────
    op.create_table(
        "provider_routing_rules",
        Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        Column("user_id", UUID(as_uuid=True), ForeignKey("users.id"), nullable=False),
        Column("provider_id", UUID(as_uuid=True), ForeignKey("user_llm_providers.id"), nullable=False),
        Column("task_type", String(30), nullable=False),
        Column("priority", Integer, default=100),
        Column("max_cost_per_request", Float, nullable=True),
        Column("min_quality_score", Float, nullable=True),
        Column("speed_priority", Boolean, default=False),
        Column("fallback_provider_id", UUID(as_uuid=True), ForeignKey("user_llm_providers.id"), nullable=True),
        Column("model_override", String(100), nullable=True),
        Column("temperature_override", Float, nullable=True),
        Column("is_active", Boolean, default=True),
        Column("created_at", DateTime(timezone=True), server_default=func.now()),
    )
    op.create_index("ix_routing_rules_user_id", "provider_routing_rules", ["user_id"])
    op.create_index("ix_routing_rules_task", "provider_routing_rules", ["user_id", "task_type"])

    # ─── User Memory ───────────────────────────────────────────────────
    op.create_table(
        "user_memories",
        Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        Column("user_id", UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True),
        Column("preferred_language", String(50), default=""),
        Column("preferred_framework", String(50), default=""),
        Column("coding_style", String(20), default=""),
        Column("commit_style", String(20), default="conventional"),
        Column("pr_style", String(20), default="detailed"),
        Column("testing_preference", String(20), default="always"),
        Column("documentation_style", String(20), default="inline"),
        Column("response_style", String(20), default="detailed"),
        Column("explanation_depth", String(20), default="balanced"),
        Column("preferred_architecture", String(50), default=""),
        Column("state_management", String(50), default=""),
        Column("dependency_injection", Boolean, default=True),
        Column("favorite_repositories", JSONB, default=list),
        Column("recent_repositories", JSONB, default=list),
        Column("favorite_models", JSONB, default=list),
        Column("pinned_conversations", JSONB, default=list),
        Column("custom_instructions", Text, default=""),
        Column("frequent_prompts", JSONB, default=list),
        Column("preferred_editor", String(50), default=""),
        Column("theme_preference", String(20), default="dark"),
        Column("notify_on_completion", Boolean, default=True),
        Column("notify_on_error", Boolean, default=True),
        Column("email_digest", String(20), default="weekly"),
        Column("total_conversations", Integer, default=0),
        Column("total_tasks_completed", Integer, default=0),
        Column("total_lines_written", Integer, default=0),
        Column("updated_at", DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
    )
    op.create_index("ix_user_memories_user_id", "user_memories", ["user_id"])

    # ─── Repository Memory ─────────────────────────────────────────────
    op.create_table(
        "repository_memories",
        Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        Column("repo_url", String(512), nullable=False, unique=True),
        Column("repo_name", String(255), default=""),
        Column("repo_owner", String(255), default=""),
        Column("tech_stack", JSONB, default=dict),
        Column("folder_structure", JSONB, default=dict),
        Column("business_rules", JSONB, default=list),
        Column("coding_standards", Text, default=""),
        Column("testing_patterns", Text, default=""),
        Column("architecture_decisions", JSONB, default=list),
        Column("previous_prs", JSONB, default=list),
        Column("recent_changes", JSONB, default=list),
        Column("known_issues", JSONB, default=list),
        Column("common_libraries", JSONB, default=list),
        Column("related_repositories", JSONB, default=list),
        Column("conversation_count", Integer, default=0),
        Column("last_conversation_at", DateTime(timezone=True), nullable=True),
        Column("key_files", JSONB, default=list),
        Column("entry_points", JSONB, default=list),
        Column("database_schema", JSONB, default=dict),
        Column("api_endpoints", JSONB, default=list),
        Column("last_analyzed_at", DateTime(timezone=True), nullable=True),
        Column("analysis_version", String(20), default=""),
        Column("created_at", DateTime(timezone=True), server_default=func.now()),
        Column("updated_at", DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
    )
    op.create_index("ix_repo_memories_url", "repository_memories", ["repo_url"])
    op.create_index("ix_repo_memories_owner", "repository_memories", ["repo_owner"])

    # ─── Organization Memory ──────────────────────────────────────────
    op.create_table(
        "organization_memories",
        Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        Column("org_id", UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False),
        Column("category", String(50), nullable=False),
        Column("title", String(255), nullable=False),
        Column("content", Text, nullable=False),
        Column("applies_to_repos", JSONB, default=list),
        Column("applies_to_languages", JSONB, default=list),
        Column("applies_to_frameworks", JSONB, default=list),
        Column("is_required", Boolean, default=False),
        Column("enforcement_level", String(20), default="suggest"),
        Column("created_by", UUID(as_uuid=True), ForeignKey("users.id"), nullable=True),
        Column("updated_by", UUID(as_uuid=True), ForeignKey("users.id"), nullable=True),
        Column("created_at", DateTime(timezone=True), server_default=func.now()),
        Column("updated_at", DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
    )
    op.create_index("ix_org_memories_org_id", "organization_memories", ["org_id"])
    op.create_index("ix_org_memories_category", "organization_memories", ["org_id", "category"])


def downgrade() -> None:
    """Remove all new tables."""
    # Drop in reverse order of creation
    op.drop_table("organization_memories")
    op.drop_table("repository_memories")
    op.drop_table("user_memories")
    op.drop_table("provider_routing_rules")
    op.drop_table("user_llm_providers")
    op.drop_table("task_events")
    op.drop_table("conversation_events")
    op.drop_table("conversation_tasks")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("user_sessions")
    op.drop_table("users")
    op.drop_table("organizations")
