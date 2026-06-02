"""DevBuddy Lite — FastAPI application entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup / shutdown lifecycle."""
    setup_logging(json=settings.ENVIRONMENT == "production")

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
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
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
