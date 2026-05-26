"""AEP API routers — public re-exports."""

from app.aep.api.admin import router as admin_router
from app.aep.api.llm_gateway import router as llm_gateway_router

__all__ = ["admin_router", "llm_gateway_router"]
