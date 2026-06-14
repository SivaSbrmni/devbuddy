"""Entry point — re-exports the FastAPI application instance.

Deploy trigger: 2026-06-14 (HF Space sync)
"""

from fastapi import FastAPI  # noqa: F401 — helps deploy-tool detection

# The real app with all routers, middleware, and lifespan is defined in app/main.py
from app.main import app  # noqa: F401

__all__ = ["app"]
