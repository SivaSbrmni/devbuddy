"""AEP (Autonomous Engineering Platform) database models.

All tables use the `aep_` prefix as required by the spec (Part 4).
These are additive — they do not modify or conflict with existing tables.

Migration: app/models/aep.py registers models on Base.metadata.
The startup table creation in main.py handles schema sync.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Column, Integer, Text, ForeignKey, Index, DateTime,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from pgvector.sqlalchemy import Vector

from app.db.base import Base


class AepTask(Base):
    """Autonomous engineering task — the unit of work for the agent pipeline."""
    __tablename__ = "aep_tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_id = Column(Text, unique=True, nullable=True)  # link to existing app's task ID
    title = Column(Text, nullable=False)
    description = Column(Text)
    status = Column(Text, nullable=False, default="pending")  # pending, planning, executing, validating, completed, failed, abandoned
    priority = Column(Integer, default=5)
    repository_id = Column(UUID(as_uuid=True), ForeignKey("aep_repositories.id"), nullable=True)
    created_by = Column(Text, nullable=False)
    tenant_id = Column(Text, nullable=False, default="default")
    feature_branch = Column(Text)
    metadata_ = Column("metadata", JSONB, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_aep_tasks_tenant", "tenant_id"),
        Index("idx_aep_tasks_status", "status"),
    )


class AepRepository(Base):
    """Registered GitHub repository for autonomous operations."""
    __tablename__ = "aep_repositories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    github_owner = Column(Text, nullable=False)
    github_repo = Column(Text, nullable=False)
    default_branch = Column(Text, default="main")
    installation_id = Column(Text)
    token_ref = Column(Text)  # reference to SecretManager key
    index_status = Column(Text, default="pending")  # pending, indexing, indexed, failed
    last_indexed_at = Column(DateTime)
    metadata_ = Column("metadata", JSONB, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_aep_repos_unique", "github_owner", "github_repo", unique=True),
    )


class AepExecution(Base):
    """Single agent execution within a task. Tracks GHA run, tokens, artifacts."""
    __tablename__ = "aep_executions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("aep_tasks.id"), nullable=True)
    agent_name = Column(Text, nullable=False)
    status = Column(Text, nullable=False, default="pending")  # pending, running, completed, failed, retrying
    workflow_run_id = Column(Text)
    branch = Column(Text)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    token_usage = Column(JSONB, default=dict)  # {input_tokens, output_tokens, cost_usd}
    tokens_saved = Column(JSONB, default=dict)  # {compressor: tokens_saved}
    provider_used = Column(Text)
    error = Column(Text)
    artifacts = Column(JSONB, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_aep_executions_task", "task_id"),
    )


class AepMemory(Base):
    """Long-term memory with vector embeddings for semantic retrieval."""
    __tablename__ = "aep_memory"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    namespace = Column(Text, nullable=False)  # e.g. 'repo:{owner}/{repo}', 'task:{id}'
    entity_id = Column(Text, nullable=False)
    memory_type = Column(Text, nullable=False)  # repo_summary, execution_history, debug_pattern, code_pattern, failure_library
    content = Column(Text, nullable=False)
    embedding = Column(Vector(768), nullable=True)  # Gemini embedding dimension
    metadata_ = Column("metadata", JSONB, default=dict)
    ttl_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_aep_memory_entity", "namespace", "entity_id"),
        # ivfflat index created via migration for production
    )


class AepWorkflow(Base):
    """Generated GitHub Actions workflow YAML for task execution."""
    __tablename__ = "aep_workflows"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("aep_tasks.id"), nullable=True)
    yaml_content = Column(Text, nullable=False)
    trigger_type = Column(Text, nullable=False)  # workflow_dispatch, repository_dispatch, push
    status = Column(Text, default="draft")  # draft, triggered, completed, failed
    run_id = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class AepPendingQueue(Base):
    """Queue for LLM requests that exhausted all providers in the cascade.

    When every free-tier provider is rate-limited, the compressed payload is
    enqueued here and retried when quota resets.
    """
    __tablename__ = "aep_pending_queue"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    execution_id = Column(UUID(as_uuid=True), ForeignKey("aep_executions.id"), nullable=True)
    compressed_payload = Column(JSONB, nullable=False)
    task_type = Column(Text, nullable=False)
    enqueued_at = Column(DateTime, default=datetime.utcnow)
    next_retry_at = Column(DateTime, nullable=True)


class AepAuditLog(Base):
    """Security audit trail for all autonomous operations."""
    __tablename__ = "aep_audit_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(Text, nullable=False, default="default")
    actor = Column(Text, nullable=False)  # user email or 'system'
    action = Column(Text, nullable=False)  # task.created, execution.started, command.executed
    resource_type = Column(Text)
    resource_id = Column(Text)
    metadata_ = Column("metadata", JSONB, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_aep_audit_tenant", "tenant_id", "created_at"),
    )
