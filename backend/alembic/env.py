"""Alembic environment — async migration runner."""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import settings
from app.db.base import Base

# Import all models so Alembic sees them
# Legacy models
from app.models.project import Project  # noqa: F401
from app.models.task import Task, Milestone, AgentStep  # noqa: F401
from app.models.execution import Run, WorkflowRun, Artifact, DebugExperiment  # noqa: F401
from app.models.memory import (  # noqa: F401
    ProjectMemory, KnowledgeEntry, Skill,
    DeploymentHistory, ModelUsage, AuditLog,
)
from app.models.user_settings import UserSettings  # noqa: F401

# New cloud-native architecture models
from app.models.user import Organization, User, UserSession  # noqa: F401
from app.models.conversation import Conversation, Message, ConversationTask, ConversationEvent, TaskEvent  # noqa: F401
from app.models.llm_provider import UserLLMProvider, ProviderRoutingRule  # noqa: F401
from app.models.user_memory import UserMemory, RepositoryMemory, OrganizationMemory  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):  # type: ignore[no-untyped-def]
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
