"""DevBuddy Lite — FastAPI application entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes.agent import router as agent_router
from app.api.routes.auth import router as auth_router
from app.api.routes.chat import router as chat_router
from app.api.routes.conversations import router as conversations_router
from app.api.routes.execution import router as execution_router
from app.api.routes.health import router as health_router
from app.api.routes.knowledge import router as knowledge_router
from app.api.routes.memory import router as memory_router
from app.api.routes.metrics import router as metrics_router
from app.api.routes.mcp import router as mcp_router
from app.api.routes.models import router as models_router
from app.api.routes.settings import router as settings_router
from app.api.routes.projects import router as projects_router
from app.api.routes.skills import router as skills_router
from app.api.routes.workspace import router as workspace_router
from app.api.routes.github import router as github_router
from app.api.routes.github_agent import router as github_agent_router
from app.api.routes.cloud_agent import router as cloud_agent_router
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.model_router import model_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup / shutdown lifecycle."""
    setup_logging(json=settings.ENVIRONMENT == "production")

    # Ensure database tables exist
    from app.db.base import Base
    from app.db.session import engine

    # Import all models so they register on Base.metadata
    # Legacy models
    import app.models.project  # noqa: F401
    import app.models.task  # noqa: F401
    import app.models.execution  # noqa: F401
    import app.models.memory  # noqa: F401
    import app.models.user_settings  # noqa: F401
    
    # New cloud-native architecture models
    import app.models.user  # noqa: F401
    import app.models.conversation  # noqa: F401
    import app.models.llm_provider  # noqa: F401
    import app.models.user_memory  # noqa: F401

    # Ensure database tables exist — tolerate partial schemas on HF Space
    # restarts where /data/pgdata persists and indexes may already exist.
    from sqlalchemy import inspect

    async with engine.begin() as conn:
        def _create_missing_tables(sync_conn):
            from sqlalchemy import text
            inspector = inspect(sync_conn)
            existing = set(inspector.get_table_names())
            all_tables = set(Base.metadata.tables.keys())
            missing = all_tables - existing
            
            if missing:
                print(f"[db init] Missing tables: {missing}")
                # Drop ALL existing indexes to avoid conflicts from partial prior runs
                idx_result = sync_conn.execute(text("SELECT indexname FROM pg_indexes WHERE schemaname = 'public' AND tablename != 'pg_stat_statements'"))
                for row in idx_result:
                    idx_name = row[0]
                    if not idx_name.endswith('_pkey') and not idx_name.endswith('_idx'):
                        sync_conn.execute(text(f"DROP INDEX IF EXISTS {idx_name}"))
                        print(f"[db init] Dropped index: {idx_name}")
                
                # Create tables in dependency order using SQLAlchemy's create_all
                # which handles FK ordering. Catch index errors and continue.
                try:
                    Base.metadata.create_all(sync_conn, checkfirst=True)
                    print(f"[db init] All tables created successfully")
                except Exception as e:
                    err_msg = str(e).lower()
                    if "already exists" in err_msg or "duplicate" in err_msg:
                        print(f"[db init] Object already exists, will retry individually: {e}")
                        # Fallback: create each table individually
                        for table in Base.metadata.sorted_tables:
                            if table.name not in existing:
                                try:
                                    table.create(sync_conn, checkfirst=True)
                                    print(f"[db init] Created table: {table.name}")
                                except Exception as te:
                                    if "already exists" in str(te).lower() or "duplicate" in str(te).lower():
                                        print(f"[db init] Skipping {table.name}: already exists")
                                    else:
                                        raise
                    else:
                        print(f"[db init] ERROR: {e}")
                        raise
            else:
                print(f"[db init] All tables exist: {existing}")

        await conn.run_sync(_create_missing_tables)

    # Initialize LLM router
    await model_router.startup()

    # Initialize GitHub Actions client
    from app.execution.github_actions import github_client

    await github_client.startup()

    # Initialize Browser Agent
    from app.browser.agent import browser_agent

    await browser_agent.startup()

    yield

    # Shutdown
    await model_router.shutdown()
    await github_client.shutdown()
    await browser_agent.shutdown()


app = FastAPI(
    title=settings.APP_NAME,
    description="Autonomous Software Engineering Platform",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "https://devbuddy.org",
        "https://www.devbuddy.org",
        "https://dev.devbuddy.org",
        "https://sivasbrmni-devbuddy.hf.space",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(health_router)
app.include_router(auth_router, prefix=settings.API_PREFIX)
app.include_router(conversations_router, prefix=settings.API_PREFIX)
app.include_router(projects_router, prefix=settings.API_PREFIX)
app.include_router(memory_router, prefix=settings.API_PREFIX)
app.include_router(skills_router, prefix=settings.API_PREFIX)
app.include_router(execution_router, prefix=settings.API_PREFIX)
app.include_router(workspace_router, prefix=settings.API_PREFIX)
app.include_router(metrics_router, prefix=settings.API_PREFIX)
app.include_router(models_router, prefix=settings.API_PREFIX)
app.include_router(chat_router, prefix=settings.API_PREFIX)
app.include_router(agent_router, prefix=settings.API_PREFIX)
app.include_router(knowledge_router, prefix=settings.API_PREFIX)
app.include_router(mcp_router, prefix=settings.API_PREFIX)
app.include_router(settings_router, prefix=settings.API_PREFIX)
app.include_router(github_router, prefix=settings.API_PREFIX)
app.include_router(github_agent_router, prefix=settings.API_PREFIX)
app.include_router(cloud_agent_router, prefix=settings.API_PREFIX)

# Migration status endpoint - MUST be before SPA fallback
@app.get("/api/v1/migration-status")
async def migration_status():
    """Check if all required tables exist in the database."""
    from sqlalchemy import inspect
    from app.db.session import engine
    
    async with engine.connect() as conn:
        def check_tables(sync_conn):
            inspector = inspect(sync_conn)
            existing = set(inspector.get_table_names())
            
            # Core new tables
            required_new = {
                'users', 'conversations', 'messages', 'conversation_tasks',
                'user_llm_providers', 'user_memories', 'repository_memories'
            }
            
            existing_required = existing & required_new
            missing = required_new - existing
            
            return {
                'all_tables_exist': len(missing) == 0,
                'existing_new_tables': list(existing_required),
                'missing_tables': list(missing),
                'total_tables_in_db': len(existing),
            }
        
        result = await conn.run_sync(check_tables)
        return result

# Serve pre-built React frontend as static files
_static_dir = Path(__file__).resolve().parent.parent / "static"
if _static_dir.is_dir():
    app.mount("/assets", StaticFiles(directory=_static_dir / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def _spa_fallback(request: Request, full_path: str) -> FileResponse:
        """Serve index.html for any non-API route (SPA client-side routing)."""
        # Don't intercept API routes
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        
        file_path = _static_dir / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(
            _static_dir / "index.html",
            headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"}
        )
