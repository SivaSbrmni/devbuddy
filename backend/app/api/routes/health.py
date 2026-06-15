"""Health check endpoint."""

from __future__ import annotations

import traceback

from fastapi import APIRouter
from sqlalchemy import text

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    """Basic liveness probe."""
    return {"status": "healthy", "service": "devbuddy-lite"}


@router.get("/health/db")
async def health_db() -> dict:
    """Deep health check — tests database connectivity."""
    try:
        from app.db.session import engine
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            result.fetchone()
        return {"status": "healthy", "database": "connected"}
    except Exception as exc:
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }


@router.get("/health/llm")
async def health_llm() -> dict:
    """Check LLM provider availability."""
    from app.core.config import settings

    return {
        "anthropic": "configured" if settings.ANTHROPIC_API_KEY else "not_configured",
        "llama": "configured" if settings.LLAMA_API_KEY else "not_configured",
        "llama_base": settings.LLAMA_API_BASE,
        "ollama": "configured" if settings.OLLAMA_API_KEY else "not_configured",
        "ollama_base": settings.OLLAMA_API_BASE,
        "ollama_model": settings.OLLAMA_MODEL,
    }


@router.get("/health/db-status")
async def health_db_status() -> dict:
    """Show database table status for diagnostics."""
    try:
        from app.db.session import engine
        from sqlalchemy import inspect
        from app.db.base import Base
        import app.models.project  # noqa: F401
        import app.models.task  # noqa: F401
        import app.models.execution  # noqa: F401
        import app.models.memory  # noqa: F401
        import app.models.user_settings  # noqa: F401

        async with engine.connect() as conn:
            def _get_tables(sync_conn):
                inspector = inspect(sync_conn)
                return inspector.get_table_names()

            result = await conn.run_sync(_get_tables)
            existing = set(result)
            expected = set(Base.metadata.tables.keys())
            missing = expected - existing

            return {
                "status": "healthy",
                "existing_tables": sorted(existing),
                "expected_tables": sorted(expected),
                "missing_tables": sorted(missing),
                "all_exist": len(missing) == 0,
            }
    except Exception as exc:
        return {
            "status": "error",
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }


@router.post("/health/db-init")
async def health_db_init() -> dict:
    """Force-create all database tables for emergency recovery."""
    try:
        from app.db.session import engine
        from sqlalchemy import inspect
        from app.db.base import Base
        import app.models.project  # noqa: F401
        import app.models.task  # noqa: F401
        import app.models.execution  # noqa: F401
        import app.models.memory  # noqa: F401
        import app.models.user_settings  # noqa: F401

        async with engine.begin() as conn:
            def _create_all(sync_conn):
                from sqlalchemy import text
                inspector = inspect(sync_conn)
                existing = set(inspector.get_table_names())
                all_tables = set(Base.metadata.tables.keys())
                missing = all_tables - existing
                if not missing:
                    return {"created": [], "existing": sorted(existing)}
                # Drop conflicting indexes from partial prior runs
                for idx in ["ix_user_settings_email", "ix_pm_project_category", "ix_ke_category", 
                            "ix_skills_category", "ix_mu_provider", "ix_audit_actor", 
                            "ix_audit_action", "ix_audit_created"]:
                    sync_conn.execute(text(f"DROP INDEX IF EXISTS {idx}"))
                try:
                    Base.metadata.create_all(sync_conn, checkfirst=True)
                except Exception:
                    for table in Base.metadata.sorted_tables:
                        if table.name not in existing:
                            try:
                                table.create(sync_conn, checkfirst=True)
                            except Exception:
                                pass
                return {"created": sorted(missing), "existing": sorted(existing)}

            result = await conn.run_sync(_create_all)

        return {
            "status": "success",
            "message": "Tables created",
            "tables": result,
        }
    except Exception as exc:
        return {
            "status": "error",
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }
