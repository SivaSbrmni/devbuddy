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
    import app.models.project  # noqa: F401
    import app.models.task  # noqa: F401
    import app.models.execution  # noqa: F401
    import app.models.memory  # noqa: F401
    import app.models.user_settings  # noqa: F401

    # Ensure database tables exist — tolerate partial schemas on HF Space
    # restarts where /data/pgdata persists and indexes may already exist.
    from sqlalchemy import inspect

    async with engine.begin() as conn:
        def _create_missing_tables(sync_conn):
            inspector = inspect(sync_conn)
            existing = set(inspector.get_table_names())
            all_tables = set(Base.metadata.tables.keys())
            missing = all_tables - existing
            
            if missing:
                print(f"[db init] Missing tables: {missing}")
                for table_name in sorted(missing):
                    table = Base.metadata.tables[table_name]
                    try:
                        table.create(sync_conn, checkfirst=True)
                        print(f"[db init] Created table: {table_name}")
                    except Exception as e:
                        err = str(e).lower()
                        if "already exists" in err or "duplicate" in err:
                            print(f"[db init] Table {table_name} already exists, skipping")
                        else:
                            print(f"[db init] ERROR creating {table_name}: {e}")
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
