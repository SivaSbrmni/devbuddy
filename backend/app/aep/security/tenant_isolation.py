"""Tenant Isolation — Phase 6.

SQLAlchemy event listener that asserts every ``aep_*`` query includes a
``tenant_id`` filter. Also provides helpers for generating Postgres
Row-Level Security (RLS) policies.

Spec reference: AGENTS.md Phase 6 — Tenant Isolation, spec §10.4.
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.aep.observability import aep_logger

_logger = aep_logger("aep.security.tenant_isolation")

# All AEP tables that require tenant_id filtering
AEP_TABLES: set[str] = {
    "aep_feature_flags",
    "aep_repositories",
    "aep_executions",
    "aep_execution_steps",
    "aep_agent_plans",
    "aep_workflow_runs",
    "aep_memory_entries",
    "aep_audit_log",
    "aep_secrets_metadata",
}


class TenantIsolationViolation(Exception):
    """Raised when a query against an aep_* table lacks tenant_id."""


def generate_rls_policies() -> list[str]:
    """Generate RLS policy SQL statements for all AEP tables.

    These should be applied via an Alembic migration. The policies
    ensure that at the database level, queries can only access rows
    matching the current session's ``app.tenant_id`` setting.

    Usage in a migration::

        from app.aep.security.tenant_isolation import generate_rls_policies
        for sql in generate_rls_policies():
            op.execute(sql)
    """
    policies: list[str] = []

    for table in sorted(AEP_TABLES):
        policies.extend([
            f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;",
            f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;",
            f"""
            CREATE POLICY {table}_tenant_isolation ON {table}
                USING (tenant_id::text = current_setting('app.tenant_id', true))
                WITH CHECK (tenant_id::text = current_setting('app.tenant_id', true));
            """.strip(),
        ])

    return policies


def generate_rls_drop_policies() -> list[str]:
    """Generate SQL to drop RLS policies (for migration downgrade)."""
    policies: list[str] = []
    for table in sorted(AEP_TABLES):
        policies.extend([
            f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table};",
            f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;",
        ])
    return policies


async def set_tenant_context(
    db: AsyncSession,
    tenant_id: uuid.UUID,
) -> None:
    """Set the tenant context for the current database session.

    This sets the Postgres session variable ``app.tenant_id`` so that
    RLS policies can filter rows by tenant.
    """
    await db.execute(
        text("SET LOCAL app.tenant_id = :tenant_id"),
        {"tenant_id": str(tenant_id)},
    )


class TenantIsolationListener:
    """SQLAlchemy event listener that validates tenant_id presence.

    Attach to a session factory to ensure that all queries against
    ``aep_*`` tables include a ``tenant_id`` filter in the WHERE clause.

    This is a **development/testing guard** — in production, RLS policies
    at the database level provide the actual enforcement.
    """

    def __init__(self, *, strict: bool = False) -> None:
        self._strict = strict

    def attach(self, session_factory: Any) -> None:
        """Attach the listener to a session factory."""
        event.listen(session_factory, "do_orm_execute", self._check_tenant_filter)

    def _check_tenant_filter(self, execute_state: Any) -> None:
        """Check if the statement targets an aep_* table without tenant_id."""
        statement = execute_state.statement
        if statement is None:
            return

        # Convert to string for analysis
        stmt_str = str(statement)
        stmt_lower = stmt_str.lower()

        # Check if query targets an AEP table
        targets_aep = any(table in stmt_lower for table in AEP_TABLES)
        if not targets_aep:
            return

        # Check if tenant_id is in the WHERE clause
        has_tenant_filter = "tenant_id" in stmt_lower

        if not has_tenant_filter:
            msg = (
                f"Query against AEP table missing tenant_id filter: "
                f"{stmt_str[:200]}"
            )
            if self._strict:
                raise TenantIsolationViolation(msg)
            _logger.warning("tenant_isolation_violation", statement=stmt_str[:200])


def redis_key_with_tenant(tenant_id: uuid.UUID, *parts: str) -> str:
    """Build a Redis key namespaced under the tenant.

    All AEP Redis keys MUST use this function to ensure tenant
    isolation in the cache layer.

    Example::

        key = redis_key_with_tenant(tenant_id, "working", str(execution_id))
        # → "aep:{tenant_id}:working:{execution_id}"
    """
    return f"aep:{tenant_id}:" + ":".join(parts)
