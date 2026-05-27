"""AEP foundation — Phase 0 (additive, namespaced aep_*)

Revision ID: 003
Revises: 002
Create Date: 2026-05-26 17:00:00.000000

Adds all infrastructure tables for the Autonomous Engineering Platform.
All tables are namespaced with the ``aep_`` prefix per the AEP spec §4.2.
Every table is additive — no existing column or index is altered.

This migration is reversible. ``downgrade()`` drops every aep_* object
in reverse FK order.

Phase 0 intentionally creates the tables but does NOT activate any
behavior on top of them — every related feature flag defaults to FALSE
in :mod:`app.aep.feature_flags`.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ─────────────────────────────────────────────────────────────────────────────
# Upgrade
# ─────────────────────────────────────────────────────────────────────────────


def upgrade() -> None:
    # ── aep_feature_flags ──────────────────────────────────────────────────
    # Per-tenant overrides for a flag; tenant_id NULL → global default.
    op.create_table(
        "aep_feature_flags",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "name", name="uq_aep_feature_flags_tenant_name"),
    )
    op.create_index(
        "ix_aep_feature_flags_name", "aep_feature_flags", ["name"]
    )
    op.create_index(
        "ix_aep_feature_flags_tenant_id", "aep_feature_flags", ["tenant_id"]
    )

    # ── aep_repositories ───────────────────────────────────────────────────
    # Registered repositories the AEP can operate on.
    op.create_table(
        "aep_repositories",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False, server_default="github"),
        sa.Column("owner", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("default_branch", sa.String(255), nullable=False, server_default="main"),
        sa.Column("auth_method", sa.String(50), nullable=False, server_default="github_app"),
        sa.Column("installation_id", sa.String(255), nullable=True),
        sa.Column("clone_url", sa.Text(), nullable=False),
        sa.Column("config", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "provider", "owner", "name",
            name="uq_aep_repositories_tenant_provider_owner_name",
        ),
    )
    op.create_index(
        "ix_aep_repositories_tenant_id", "aep_repositories", ["tenant_id"]
    )

    # ── aep_executions ─────────────────────────────────────────────────────
    # Top-level AEP autonomous-engineering executions. Distinct from the
    # existing ``agent_executions`` table (which tracks per-iteration ReAct
    # turns of the legacy single-agent executor); ``aep_executions`` is the
    # multi-agent orchestrated execution record.
    op.create_table(
        "aep_executions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("repository_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("state", sa.String(50), nullable=False, server_default="PENDING"),
        sa.Column("branch", sa.String(255), nullable=True),
        sa.Column("commit_sha", sa.String(64), nullable=True),
        sa.Column("workflow_run_id", sa.String(64), nullable=True),
        sa.Column("token_input", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("token_output", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("execution_metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["repository_id"], ["aep_repositories.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_aep_executions_tenant_id", "aep_executions", ["tenant_id"])
    op.create_index("ix_aep_executions_task_id", "aep_executions", ["task_id"])
    op.create_index("ix_aep_executions_state", "aep_executions", ["state"])
    op.create_index(
        "ix_aep_executions_created_at", "aep_executions", ["created_at"]
    )

    # ── aep_execution_steps ────────────────────────────────────────────────
    # One row per agent invocation inside an aep_execution.
    op.create_table(
        "aep_execution_steps",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("execution_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("step_index", sa.Integer(), nullable=False),
        sa.Column("agent_name", sa.String(100), nullable=False),
        sa.Column("model", sa.String(100), nullable=True),
        sa.Column("state", sa.String(50), nullable=False, server_default="PENDING"),
        sa.Column("input", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("output", postgresql.JSONB(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("token_input", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("token_output", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["execution_id"], ["aep_executions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "execution_id", "step_index", name="uq_aep_execution_steps_exec_idx"
        ),
    )
    op.create_index(
        "ix_aep_execution_steps_execution_id", "aep_execution_steps", ["execution_id"]
    )
    op.create_index(
        "ix_aep_execution_steps_tenant_id", "aep_execution_steps", ["tenant_id"]
    )
    op.create_index(
        "ix_aep_execution_steps_agent_name", "aep_execution_steps", ["agent_name"]
    )

    # ── aep_agent_plans ────────────────────────────────────────────────────
    # Stored Planner output (DAG, agent assignments, estimated cost).
    op.create_table(
        "aep_agent_plans",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("execution_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("plan", postgresql.JSONB(), nullable=False),
        sa.Column("estimated_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_steps", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("requires_github_actions", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["execution_id"], ["aep_executions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "execution_id", "version", name="uq_aep_agent_plans_exec_version"
        ),
    )
    op.create_index(
        "ix_aep_agent_plans_execution_id", "aep_agent_plans", ["execution_id"]
    )

    # ── aep_workflow_runs ──────────────────────────────────────────────────
    # GitHub Actions workflow runs triggered by AEP.
    op.create_table(
        "aep_workflow_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("execution_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("repository_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider", sa.String(50), nullable=False, server_default="github_actions"),
        sa.Column("run_id", sa.String(64), nullable=True),
        sa.Column("workflow_name", sa.String(255), nullable=False),
        sa.Column("branch", sa.String(255), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="queued"),
        sa.Column("conclusion", sa.String(50), nullable=True),
        sa.Column("html_url", sa.Text(), nullable=True),
        sa.Column("logs_excerpt", sa.Text(), nullable=True),
        sa.Column("workflow_yaml", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["execution_id"], ["aep_executions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["repository_id"], ["aep_repositories.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_aep_workflow_runs_execution_id", "aep_workflow_runs", ["execution_id"]
    )
    op.create_index(
        "ix_aep_workflow_runs_tenant_id", "aep_workflow_runs", ["tenant_id"]
    )
    op.create_index("ix_aep_workflow_runs_run_id", "aep_workflow_runs", ["run_id"])

    # ── aep_memory_entries ─────────────────────────────────────────────────
    # Long-term memory for the AEP — distinct from the existing
    # ``agent_memories`` table (which is conversational memory for the
    # legacy executor). pgvector is *not* yet enabled in Phase 0; the
    # ``embedding`` column is stored as TEXT (JSON-encoded float array)
    # and will be migrated to ``vector(N)`` in Phase 4.
    op.create_table(
        "aep_memory_entries",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("repository_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("memory_type", sa.String(50), nullable=False),
        sa.Column("key", sa.String(512), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", sa.Text(), nullable=True),
        sa.Column("embedding_model", sa.String(100), nullable=True),
        sa.Column("token_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("extra_meta", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["repository_id"], ["aep_repositories.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_aep_memory_entries_tenant_id", "aep_memory_entries", ["tenant_id"]
    )
    op.create_index(
        "ix_aep_memory_entries_memory_type", "aep_memory_entries", ["memory_type"]
    )
    op.create_index(
        "ix_aep_memory_entries_repository_id",
        "aep_memory_entries",
        ["repository_id"],
    )

    # ── aep_audit_log ──────────────────────────────────────────────────────
    # AEP-specific audit log. Hash-chained for tamper evidence.
    # Distinct from the existing ``audit_logs`` table (which tracks
    # platform-level events); ``aep_audit_log`` is the autonomous-engine
    # audit trail and is queryable independently for compliance reviews.
    op.create_table(
        "aep_audit_log",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("execution_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("actor_type", sa.String(50), nullable=False),
        sa.Column("actor_id", sa.String(255), nullable=True),
        sa.Column("resource_type", sa.String(100), nullable=True),
        sa.Column("resource_id", sa.String(255), nullable=True),
        sa.Column("action", sa.String(255), nullable=False),
        sa.Column("outcome", sa.String(50), nullable=False),
        sa.Column("details", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("previous_hash", sa.String(64), nullable=True),
        sa.Column("entry_hash", sa.String(64), nullable=False),
        sa.Column("trace_id", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["execution_id"], ["aep_executions.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_aep_audit_log_tenant_id", "aep_audit_log", ["tenant_id"])
    op.create_index("ix_aep_audit_log_event_type", "aep_audit_log", ["event_type"])
    op.create_index(
        "ix_aep_audit_log_execution_id", "aep_audit_log", ["execution_id"]
    )
    op.create_index("ix_aep_audit_log_created_at", "aep_audit_log", ["created_at"])

    # ── aep_secrets_metadata ───────────────────────────────────────────────
    # Stores *metadata* about secrets. Actual values must live in an
    # external secret manager (GitHub Secrets, Cloud Secret Manager, etc.)
    # The application MUST NOT persist plaintext values in this table.
    op.create_table(
        "aep_secrets_metadata",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scope", sa.String(50), nullable=False, server_default="tenant"),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False, server_default="env"),
        sa.Column("external_ref", sa.String(512), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("last_rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "scope", "name",
            name="uq_aep_secrets_metadata_tenant_scope_name",
        ),
    )
    op.create_index(
        "ix_aep_secrets_metadata_tenant_id", "aep_secrets_metadata", ["tenant_id"]
    )


# ─────────────────────────────────────────────────────────────────────────────
# Downgrade
# ─────────────────────────────────────────────────────────────────────────────


def downgrade() -> None:
    # Drop in reverse FK dependency order. Indexes are dropped implicitly
    # when their owning table is dropped, but we drop the explicitly named
    # ones first for clarity and to avoid surprises on partial failures.
    op.drop_index(
        "ix_aep_secrets_metadata_tenant_id", table_name="aep_secrets_metadata"
    )
    op.drop_table("aep_secrets_metadata")

    op.drop_index("ix_aep_audit_log_created_at", table_name="aep_audit_log")
    op.drop_index("ix_aep_audit_log_execution_id", table_name="aep_audit_log")
    op.drop_index("ix_aep_audit_log_event_type", table_name="aep_audit_log")
    op.drop_index("ix_aep_audit_log_tenant_id", table_name="aep_audit_log")
    op.drop_table("aep_audit_log")

    op.drop_index(
        "ix_aep_memory_entries_repository_id", table_name="aep_memory_entries"
    )
    op.drop_index(
        "ix_aep_memory_entries_memory_type", table_name="aep_memory_entries"
    )
    op.drop_index(
        "ix_aep_memory_entries_tenant_id", table_name="aep_memory_entries"
    )
    op.drop_table("aep_memory_entries")

    op.drop_index("ix_aep_workflow_runs_run_id", table_name="aep_workflow_runs")
    op.drop_index(
        "ix_aep_workflow_runs_tenant_id", table_name="aep_workflow_runs"
    )
    op.drop_index(
        "ix_aep_workflow_runs_execution_id", table_name="aep_workflow_runs"
    )
    op.drop_table("aep_workflow_runs")

    op.drop_index(
        "ix_aep_agent_plans_execution_id", table_name="aep_agent_plans"
    )
    op.drop_table("aep_agent_plans")

    op.drop_index(
        "ix_aep_execution_steps_agent_name", table_name="aep_execution_steps"
    )
    op.drop_index(
        "ix_aep_execution_steps_tenant_id", table_name="aep_execution_steps"
    )
    op.drop_index(
        "ix_aep_execution_steps_execution_id", table_name="aep_execution_steps"
    )
    op.drop_table("aep_execution_steps")

    op.drop_index("ix_aep_executions_created_at", table_name="aep_executions")
    op.drop_index("ix_aep_executions_state", table_name="aep_executions")
    op.drop_index("ix_aep_executions_task_id", table_name="aep_executions")
    op.drop_index("ix_aep_executions_tenant_id", table_name="aep_executions")
    op.drop_table("aep_executions")

    op.drop_index(
        "ix_aep_repositories_tenant_id", table_name="aep_repositories"
    )
    op.drop_table("aep_repositories")

    op.drop_index(
        "ix_aep_feature_flags_tenant_id", table_name="aep_feature_flags"
    )
    op.drop_index("ix_aep_feature_flags_name", table_name="aep_feature_flags")
    op.drop_table("aep_feature_flags")
