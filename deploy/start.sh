#!/bin/bash
set -e

PGDATA="${PGDATA:-/data/pgdata}"
PG_USER="devbuddy"
PG_DB="devbuddy"

# Initialize PostgreSQL data directory if it doesn't exist
if [ ! -f "$PGDATA/PG_VERSION" ]; then
    echo "Initializing PostgreSQL data directory..."
    mkdir -p "$PGDATA"
    chown postgres:postgres "$PGDATA"
    su postgres -c "/usr/lib/postgresql/16/bin/initdb -D $PGDATA"

    # Configure PostgreSQL for local connections
    echo "host all all 127.0.0.1/32 trust" >> "$PGDATA/pg_hba.conf"
    echo "listen_addresses = '127.0.0.1'" >> "$PGDATA/postgresql.conf"
    echo "port = 5432" >> "$PGDATA/postgresql.conf"

    # Start PostgreSQL temporarily to create user and database
    su postgres -c "/usr/lib/postgresql/16/bin/pg_ctl -D $PGDATA start -w"
    su postgres -c "psql -c \"CREATE USER $PG_USER WITH PASSWORD '$PG_USER';\""
    su postgres -c "psql -c \"CREATE DATABASE $PG_DB OWNER $PG_USER;\""
    su postgres -c "psql -d $PG_DB -c 'CREATE EXTENSION IF NOT EXISTS vector;'"
    su postgres -c "/usr/lib/postgresql/16/bin/pg_ctl -D $PGDATA stop -w"
    echo "PostgreSQL initialized."
else
    echo "PostgreSQL data directory already exists."
    chown -R postgres:postgres "$PGDATA"
fi

# Start PostgreSQL in the background
echo "Starting PostgreSQL..."
su postgres -c "/usr/lib/postgresql/16/bin/pg_ctl -D $PGDATA start -w"

# Wait for PostgreSQL to be ready
for i in $(seq 1 30); do
    if su postgres -c "pg_isready -h 127.0.0.1" > /dev/null 2>&1; then
        echo "PostgreSQL is ready."
        break
    fi
    echo "Waiting for PostgreSQL... ($i/30)"
    sleep 1
done

# Drop conflicting index if it exists (prevents create_all crash on HF Space restart)
echo "Checking for conflicting indexes..."
su postgres -c "psql -d devbuddy -c 'DROP INDEX IF EXISTS ix_user_settings_email;'" > /dev/null 2>&1 || true

# Ensure all tables exist (handles schema changes on HF Space restarts)
echo "Ensuring database tables exist..."
cd /app
python3 -c "
import asyncio
import os
import sys
os.environ['DATABASE_URL'] = 'postgresql+asyncpg://devbuddy:devbuddy@127.0.0.1:5432/devbuddy'
os.environ['ENVIRONMENT'] = 'production'

from app.db.base import Base
from app.db.session import engine

# Import all models to register them
import app.models.project
import app.models.task
import app.models.execution
import app.models.memory
import app.models.user_settings
import app.models.user
import app.models.conversation
import app.models.llm_provider
import app.models.user_memory
import app.models.aep  # AEP (Autonomous Engineering Platform) models

async def create_tables():
    async with engine.begin() as conn:
        from sqlalchemy import inspect
        result = await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_table_names())
        existing = set(result)
        print(f'[start.sh] Existing tables: {existing}', flush=True)
        
        all_tables = set(Base.metadata.tables.keys())
        missing = all_tables - existing
        
        if missing:
            print(f'[start.sh] Creating missing tables: {missing}', flush=True)
            # Use create_all for proper dependency ordering (FKs handled correctly)
            def _safe_create_all(sync_conn):
                try:
                    Base.metadata.create_all(sync_conn, checkfirst=True)
                except Exception as e:
                    err = str(e).lower()
                    if 'already exists' in err or 'duplicate' in err:
                        print(f'[start.sh] Some objects already exist, continuing', flush=True)
                    else:
                        raise
            await conn.run_sync(_safe_create_all)
            print(f'[start.sh] Tables created successfully', flush=True)
        else:
            print(f'[start.sh] All tables already exist', flush=True)

asyncio.run(create_tables())
" || { echo "CRITICAL: Table creation failed!"; exit 1; }

# Set production defaults
export ENVIRONMENT="${ENVIRONMENT:-production}"
export DEBUG="${DEBUG:-false}"
if [ -z "$SECRET_KEY" ]; then
    if [ "$ENVIRONMENT" = "production" ]; then
        echo "ERROR: SECRET_KEY must be set as a HuggingFace Space secret"
        exit 1
    fi
    export SECRET_KEY="devbuddy-local-dev-only"
fi

# Start FastAPI application
echo "Starting DevBuddy Lite..."
exec uvicorn main:app --host 0.0.0.0 --port 7860
