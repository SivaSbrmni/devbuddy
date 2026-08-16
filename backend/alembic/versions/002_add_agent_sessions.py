"""Add agent session tables for Devin-style execution."""

from __future__ import annotations

from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("conversation_id", UUID(as_uuid=True), sa.ForeignKey("conversations.id"), nullable=True),
        sa.Column("title", sa.String(255), nullable=False, server_default="New session"),
        sa.Column("prompt", sa.Text(), nullable=False, server_default=""),
        sa.Column("mode", sa.String(20), nullable=False, server_default="session"),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("repository_url", sa.String(512), nullable=True),
        sa.Column("repository_owner", sa.String(255), nullable=True),
        sa.Column("repository_name", sa.String(255), nullable=True),
        sa.Column("branch", sa.String(255), nullable=True),
        sa.Column("plan", JSONB(), nullable=False, server_default="{}"),
        sa.Column("current_step_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("step_summaries", JSONB(), nullable=False, server_default="[]"),
        sa.Column("devbox_type", sa.String(32), nullable=False, server_default="github_actions"),
        sa.Column("devbox_ref", sa.String(255), nullable=True),
        sa.Column("github_run_id", sa.Integer(), nullable=True),
        sa.Column("github_run_url", sa.String(512), nullable=True),
        sa.Column("pr_url", sa.String(512), nullable=True),
        sa.Column("pr_number", sa.Integer(), nullable=True),
        sa.Column("result", JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_agent_sessions_user_id", "agent_sessions", ["user_id"])
    op.create_index("ix_agent_sessions_status", "agent_sessions", ["user_id", "status"])
    op.create_index("ix_agent_sessions_conversation", "agent_sessions", ["conversation_id"])

    op.create_table(
        "session_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "session_id",
            UUID(as_uuid=True),
            sa.ForeignKey("agent_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("payload", JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("session_id", "seq", name="uq_session_events_session_seq"),
    )
    op.create_index("ix_session_events_session_seq", "session_events", ["session_id", "seq"])


def downgrade() -> None:
    op.drop_index("ix_session_events_session_seq", table_name="session_events")
    op.drop_table("session_events")
    op.drop_index("ix_agent_sessions_conversation", table_name="agent_sessions")
    op.drop_index("ix_agent_sessions_status", table_name="agent_sessions")
    op.drop_index("ix_agent_sessions_user_id", table_name="agent_sessions")
    op.drop_table("agent_sessions")
