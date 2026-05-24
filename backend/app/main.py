import os
import time
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
import structlog.contextvars

from app.core.config import settings
from app.core.logger import setup_logging, get_logger
from app.core.database import engine
from app.core.ratelimit import limiter
from app.api import auth, tasks, audit, logs, chat, workspace, llm_config, mcp_connections, github_connections, memory

setup_logging()
logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("startup", app=settings.APP_NAME, env=settings.ENVIRONMENT)
    # NOTE: Schema is managed by Alembic migrations (see alembic/versions/).
    # In production: `alembic upgrade head` runs as part of the deploy pipeline.
    # In dev: opt-in auto-create via AUTO_CREATE_TABLES=1 for fast iteration.
    if os.environ.get("AUTO_CREATE_TABLES") == "1":
        from app.core.database import Base  # local import to keep prod import light
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.warning("auto_create_tables_dev_only")
    logger.info("startup_complete")
    yield
    logger.info("shutdown")
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# ── Sentry (optional) ─────────────────────────────────────────────────────────
SENTRY_DSN = os.environ.get("SENTRY_DSN", "").strip()
if SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration

        sentry_sdk.init(
            dsn=SENTRY_DSN,
            integrations=[FastApiIntegration()],
            traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
            environment=settings.ENVIRONMENT,
            release=os.environ.get("RELEASE_SHA", "dev"),
        )
        logger.info("sentry_initialized")
    except Exception as exc:  # noqa: BLE001
        logger.warning("sentry_init_failed", error=str(exc))

# ── Rate limiting ─────────────────────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# ── CORS ──────────────────────────────────────────────────────────────────────
_default_origins = "http://localhost:5173,http://localhost:3000,https://devbuddy.org,https://app.devbuddy.org,https://devbuddy.pages.dev"
allow_origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", _default_origins).split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Trace-ID"],
)


@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    trace_id = str(uuid.uuid4())
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(trace_id=trace_id, path=request.url.path, method=request.method)
    start = time.time()
    response = await call_next(request)
    duration_ms = round((time.time() - start) * 1000, 2)
    logger.info("http_request", status_code=response.status_code, duration_ms=duration_ms)
    response.headers["X-Trace-ID"] = trace_id
    return response


app.include_router(auth.router, prefix="/api/v1")
app.include_router(tasks.router, prefix="/api/v1")
app.include_router(audit.router, prefix="/api/v1")
app.include_router(logs.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(workspace.router, prefix="/api/v1")
app.include_router(llm_config.router, prefix="/api/v1")
app.include_router(mcp_connections.router, prefix="/api/v1")
app.include_router(github_connections.router, prefix="/api/v1")
app.include_router(memory.router, prefix="/api/v1")


@app.get("/health")
@app.get("/api/health")
async def health():
    return {"status": "ok", "app": settings.APP_NAME, "env": settings.ENVIRONMENT}
