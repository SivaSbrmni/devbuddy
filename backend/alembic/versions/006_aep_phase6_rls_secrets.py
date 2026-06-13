"""Phase 6 — RLS policies + secrets encrypted_value column.

Revision ID: 006
Revises: 005
Create Date: 2026-06-13 16:00:00.000000

Adds:
    1. Row-Level Security policies on all aep_* tables.
    2. ``encrypted_value`` column to ``aep_secrets_metadata``.
    3. Unique constraint on (tenant_id, name) for secrets.

Spec reference: AGENTS.md Phase 6 — Tenant Isolation, SecretManager.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

AEP_TABLES = [
    "aep_audit_log",
    "aep_agent_plans",
    "aep_execution_steps",
    "aep_executions",
    "aep_feature_flags",
    "aep_memory_entries",
    "aep_repositories",
    "aep_secrets_metadata",
    "aep_workflow_runs",
]


def upgrade() -> None:
    # ── Secrets: add encrypted_value column ────────────────────────────────
    op.execute(
        "ALTER TABLE aep_secrets_metadata "
        "ADD COLUMN IF NOT EXISTS encrypted_value TEXT;"
    )

    # Unique constraint on (tenant_id, name) for upsert support
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_aep_secrets_tenant_name "
        "ON aep_secrets_metadata (tenant_id, name);"
    )

    # ── Row-Level Security ─────────────────────────────────────────────────
    for table in AEP_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")
        op.execute(
            f"CREATE POLICY {table}_tenant_isolation ON {table} "
            f"USING (tenant_id::text = current_setting('app.tenant_id', true)) "
            f"WITH CHECK (tenant_id::text = current_setting('app.tenant_id', true));"
        )


def downgrade() -> None:
    # ── Drop RLS policies ──────────────────────────────────────────────────
    for table in AEP_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table};")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")

    # ── Drop secrets changes ───────────────────────────────────────────────
    op.execute("DROP INDEX IF EXISTS uq_aep_secrets_tenant_name;")
    op.execute(
        "ALTER TABLE aep_secrets_metadata "
        "DROP COLUMN IF EXISTS encrypted_value;"
    )
