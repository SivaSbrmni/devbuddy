import time
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import structlog.contextvars

from app.core.config import settings
from app.core.logger import setup_logging, get_logger
from app.core.database import engine, Base
from app.api import auth, tasks, audit, logs

setup_logging()
logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("startup", app=settings.APP_NAME, env=settings.ENVIRONMENT)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("database_tables_ready")
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "https://devbuddy.org", "https://app.devbuddy.org"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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


@app.get("/health")
@app.get("/api/health")
async def health():
    return {"status": "ok", "app": settings.APP_NAME, "env": settings.ENVIRONMENT}
