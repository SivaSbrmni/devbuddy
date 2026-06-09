"""Async SQLAlchemy engine & session factory."""

from __future__ import annotations

import ssl as _ssl

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

# Cloud Postgres providers (Supabase, Neon, etc.) require SSL;
# localhost connections (embedded Postgres) do not.
_connect_args: dict = {}
_is_remote = "supabase" in settings.DATABASE_URL or (
    "localhost" not in settings.DATABASE_URL and "127.0.0.1" not in settings.DATABASE_URL
)
if _is_remote and settings.ENVIRONMENT == "production":
    _ssl_ctx = _ssl.create_default_context()
    _ssl_ctx.check_hostname = False
    _ssl_ctx.verify_mode = _ssl.CERT_NONE
    _connect_args["ssl"] = _ssl_ctx

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=5,
    max_overflow=10,
    connect_args=_connect_args,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
