"""DevBuddy Lite — FastAPI application entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.api.routes.execution import router as execution_router
from app.api.routes.health import router as health_router
from app.api.routes.memory import router as memory_router
from app.api.routes.metrics import router as metrics_router
from app.api.routes.projects import router as projects_router
from app.api.routes.skills import router as skills_router
from app.api.routes.workspace import router as workspace_router
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.model_router import model_router

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup / shutdown lifecycle."""
    setup_logging(json=settings.ENVIRONMENT == "production")

    # Auto-create database tables if they don't exist
    try:
        from app.db.base import Base
        from app.db.session import engine
        import app.models.project  # noqa: F401
        import app.models.task  # noqa: F401
        import app.models.execution  # noqa: F401
        import app.models.memory  # noqa: F401

        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables ensured")
    except Exception as exc:
        logger.warning("Database init skipped: %s", exc)

    # Initialize LLM router
    await model_router.startup()

    # Initialize GitHub Actions client (graceful)
    try:
        from app.execution.github_actions import github_client
        await github_client.startup()
    except Exception as exc:
        logger.warning("GitHub client init skipped: %s", exc)

    # Initialize Browser Agent (graceful — Playwright may not be installed)
    try:
        from app.browser.agent import browser_agent
        await browser_agent.startup()
    except Exception as exc:
        logger.warning("Browser agent init skipped: %s", exc)

    yield

    # Shutdown
    await model_router.shutdown()
    try:
        from app.execution.github_actions import github_client
        await github_client.shutdown()
    except Exception:
        pass
    try:
        from app.browser.agent import browser_agent
        await browser_agent.shutdown()
    except Exception:
        pass


app = FastAPI(
    title=settings.APP_NAME,
    description="Autonomous Software Engineering Platform",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
_cors_origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    "https://devbuddy.org",
    "https://www.devbuddy.org",
]
if settings.CORS_ORIGINS:
    _cors_origins.extend(settings.CORS_ORIGINS.split(","))
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(health_router)
app.include_router(projects_router, prefix=settings.API_PREFIX)
app.include_router(memory_router, prefix=settings.API_PREFIX)
app.include_router(skills_router, prefix=settings.API_PREFIX)
app.include_router(execution_router, prefix=settings.API_PREFIX)
app.include_router(workspace_router, prefix=settings.API_PREFIX)
app.include_router(metrics_router, prefix=settings.API_PREFIX)

# --- Static file serving (production: built frontend) ---
if STATIC_DIR.exists() and (STATIC_DIR / "index.html").exists():
    # Mount /assets for hashed JS/CSS bundles
    assets_dir = STATIC_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="static-assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        """SPA catch-all — serve static file or fall back to index.html."""
        file_path = STATIC_DIR / full_path
        if full_path and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(STATIC_DIR / "index.html")
