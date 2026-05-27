"""
Tests for the AEP SQLAlchemy models.

We verify three properties:

  1. Every ``aep_*`` model is registered against the shared
     :data:`app.core.database.Base.metadata` (so Alembic and
     ``Base.metadata.create_all`` see it).
  2. The corresponding tables can be created and dropped through the
     standard ``create_all`` / ``drop_all`` flow used by the test
     conftest — i.e. our models do not contradict the migration's
     column definitions.
  3. Foreign-key relationships round-trip through the ORM.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import Base
from app.models.tenant import Tenant
from app.aep.models import (
    AepAuditLog,
    AepExecution,
    AepExecutionState,
    AepFeatureFlag,
    AepMemoryEntry,
    AepSecretMetadata,
)


class TestModelRegistration:
    def test_aep_tables_registered_with_metadata(self):
        tables = {t.name for t in Base.metadata.sorted_tables}
        expected = {
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
        missing = expected - tables
        assert not missing, f"aep_* tables missing from metadata: {missing}"

    def test_existing_tables_unchanged(self):
        """The existing platform tables must still be registered."""
        tables = {t.name for t in Base.metadata.sorted_tables}
        for required in (
            "tenants",
            "users",
            "tasks",
            "task_events",
            "agent_executions",
            "audit_logs",
            "agent_memories",
        ):
            assert required in tables, f"existing table dropped: {required}"


class TestPersistence:
    async def test_feature_flag_round_trip(self, db_session: AsyncSession):
        row = AepFeatureFlag(
            name="autonomous_engine_enabled",
            enabled=True,
            description="test",
        )
        db_session.add(row)
        await db_session.flush()

        fetched = (
            await db_session.execute(
                select(AepFeatureFlag).where(
                    AepFeatureFlag.name == "autonomous_engine_enabled"
                )
            )
        ).scalar_one()
        assert fetched.enabled is True
        assert fetched.tenant_id is None

    async def test_execution_links_to_tenant(self, db_session: AsyncSession):
        tenant = Tenant(name="ACME", slug=f"acme-{uuid.uuid4().hex[:8]}")
        db_session.add(tenant)
        await db_session.flush()

        execution = AepExecution(
            tenant_id=tenant.id,
            title="Test execution",
            state=AepExecutionState.PENDING.value,
        )
        db_session.add(execution)
        await db_session.flush()

        fetched = (
            await db_session.execute(
                select(AepExecution).where(AepExecution.id == execution.id)
            )
        ).scalar_one()
        assert fetched.tenant_id == tenant.id
        assert fetched.state == "PENDING"
        assert fetched.token_input == 0
        assert fetched.retry_count == 0

    async def test_audit_log_hash_chain_fields(self, db_session: AsyncSession):
        tenant = Tenant(name="A", slug=f"a-{uuid.uuid4().hex[:8]}")
        db_session.add(tenant)
        await db_session.flush()

        entry = AepAuditLog(
            tenant_id=tenant.id,
            event_type="flag.update",
            actor_type="user",
            actor_id="alice",
            action="set",
            outcome="success",
            entry_hash="0" * 64,
            previous_hash=None,
        )
        db_session.add(entry)
        await db_session.flush()

        fetched = (
            await db_session.execute(
                select(AepAuditLog).where(AepAuditLog.id == entry.id)
            )
        ).scalar_one()
        assert fetched.entry_hash == "0" * 64
        assert fetched.previous_hash is None
        assert fetched.details == {}

    async def test_secret_metadata_never_carries_plaintext(self, db_session: AsyncSession):
        """Sanity check: the model has no plaintext value column at all."""
        tenant = Tenant(name="B", slug=f"b-{uuid.uuid4().hex[:8]}")
        db_session.add(tenant)
        await db_session.flush()

        meta = AepSecretMetadata(
            tenant_id=tenant.id,
            scope="tenant",
            name="GITHUB_TOKEN",
            provider="github_secrets",
            external_ref="repo/owner",
        )
        db_session.add(meta)
        await db_session.flush()

        # Model definition must not expose any plaintext field.
        columns = {c.name for c in AepSecretMetadata.__table__.columns}
        for forbidden in ("value", "secret", "plaintext", "token", "password"):
            assert forbidden not in columns, (
                f"aep_secrets_metadata exposes a forbidden column {forbidden!r} "
                f"— secret values must live in an external manager only."
            )

    async def test_memory_entry_embedding_text_not_vector(self, db_session: AsyncSession):
        """Phase 0 stores embeddings as JSON text — migration to pgvector lands in Phase 4."""
        column = AepMemoryEntry.__table__.columns["embedding"]
        assert str(column.type).upper().startswith("TEXT"), (
            "Phase 0 must store embeddings as TEXT — pgvector is enabled in Phase 4."
        )
