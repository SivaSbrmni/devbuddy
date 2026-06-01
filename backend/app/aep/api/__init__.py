"""AEP API routers — public re-exports."""

from app.aep.api.admin import router as admin_router
from app.aep.api.llm_gateway import router as llm_gateway_router
from app.aep.api.github_webhooks import router as github_webhooks_router
from app.aep.api.repositories import router as repositories_router
from app.aep.api.executions import router as executions_router

__all__ = [
    "admin_router",
    "llm_gateway_router",
    "github_webhooks_router",
    "repositories_router",
    "executions_router",
]
