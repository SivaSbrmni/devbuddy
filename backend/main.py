"""Entry point — re-exports the FastAPI application instance."""



from fastapi import FastAPI  # noqa: F401 — helps deploy-tool detection

# The real app with all routers, middleware, and lifespan is defined in app/main.py
from app.main import app  # noqa: F401

__all__ = ["app"]
