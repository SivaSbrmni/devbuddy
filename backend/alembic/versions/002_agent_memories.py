"""add agent_memories table

Revision ID: 002
Revises: 001
Create Date: 2026-05-24 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_memories",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.String(255), nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("source", sa.String(64), nullable=False, server_default="conversation"),
        sa.Column("vector", sa.Text, nullable=False),
        sa.Column("extra_meta", sa.Text, nullable=True, server_default="{}"),
        sa.Column("created_at", sa.Float, nullable=False, server_default="0"),
    )
    op.create_index("ix_agent_memories_user_id", "agent_memories", ["user_id"])
    op.create_index("ix_agent_memories_user_created", "agent_memories", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_agent_memories_user_created", table_name="agent_memories")
    op.drop_index("ix_agent_memories_user_id", table_name="agent_memories")
    op.drop_table("agent_memories")
