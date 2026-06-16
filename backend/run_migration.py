#!/usr/bin/env python3
"""Run database migration programmatically."""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import text
from app.db.session import engine, async_session_factory
from app.db.base import Base

# Import all models to register them with Base.metadata
from app.models import *  # noqa: F403

async def check_tables_exist():
    """Check if new tables already exist."""
    async with async_session_factory() as db:
        result = await db.execute(text("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name IN ('users', 'conversations', 'messages')
        """))
        tables = [row[0] for row in result.all()]
        return len(tables) > 0

async def run_migration():
    """Create all tables from SQLAlchemy models."""
    print("Checking current database state...")

    tables_exist = await check_tables_exist()
    if tables_exist:
        print("✅ Tables already exist - migration already applied")
        return

    print("Creating tables from SQLAlchemy models...")
    print("This may take a moment...")

    async with engine.begin() as conn:
        # Create all tables registered with Base.metadata
        await conn.run_sync(Base.metadata.create_all)

    print("✅ Migration complete!")
    print("\nCreated tables:")

    async with async_session_factory() as db:
        result = await db.execute(text("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name IN (
                'organizations', 'users', 'user_sessions',
                'conversations', 'messages', 'conversation_tasks',
                'conversation_events', 'task_events',
                'user_llm_providers', 'provider_routing_rules',
                'user_memories', 'repository_memories', 'organization_memories'
            )
            ORDER BY table_name
        """))
        tables = [row[0] for row in result.all()]
        for table in tables:
            print(f"  ✓ {table}")

    print(f"\nTotal new tables: {len(tables)}")

if __name__ == "__main__":
    asyncio.run(run_migration())
