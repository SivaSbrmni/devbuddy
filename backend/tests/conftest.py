"""Test configuration."""

import os

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://devbuddy:devbuddy@localhost:5432/devbuddy_test")
os.environ.setdefault("SECRET_KEY", "test-secret-32-chars-long-enough!")
os.environ.setdefault("ANTHROPIC_API_KEY", "")
os.environ.setdefault("LLAMA_API_KEY", "")
