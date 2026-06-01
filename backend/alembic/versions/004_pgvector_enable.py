"""Enable pgvector extension — Phase 4

Revision ID: 004
Revises: 003
Create Date: 2026-06-01 06:00:00.000000

Enables the ``vector`` extension for Postgres. This is a no-op on
Supabase or Cloud SQL instances where pgvector is already enabled.
On vanilla Postgres, the superuser must have installed the pgvector
package (``apt install postgresql-16-pgvector`` or equivalent).
"""
from typing import Sequence, Union

from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS vector;")
