"""
Pytest fixtures and test utilities.
"""
import os
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

# Ensure test env vars before importing app
os.environ.setdefault("SECRET_KEY", "test-secret-key-32-chars-long!")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://devbuddy:devbuddy@localhost:5432/devbuddy_test")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "test-anon-key")
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-jwt-secret-32-chars-long!!")
os.environ.setdefault("ENVIRONMENT", "test")

from app.main import app  # noqa: E402
from app.core.database import Base  # noqa: E402


@pytest_asyncio.fixture(scope="function")
async def db_engine():
    """Create a test database engine with fresh schema per test."""
    url = os.environ["DATABASE_URL"]
    engine = create_async_engine(url, echo=False, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(db_engine):
    """Provide a transactional scope around tests."""
    async_session = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(scope="function")
async def client(db_engine):
    """Async HTTP client for FastAPI tests."""
    # Override the app's get_db dependency if needed in future
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
def mock_user_token():
    """A dummy JWT for testing (not cryptographically valid, just for structure)."""
    # In real tests you'd mock the auth or use a test Supabase project
    return "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0LXVzZXItaWQiLCJlbWFpbCI6InRlc3RAdGVzdC5jb20iLCJ0ZW5hbnRfaWQiOiJ0ZXN0LXRlbmFudCJ9.test"
