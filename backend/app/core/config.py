"""Central configuration — loaded once from environment / .env file."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Application ---
    APP_NAME: str = "DevBuddy Lite"
    ENVIRONMENT: Literal["development", "staging", "production", "test"] = "development"
    DEBUG: bool = False
    SECRET_KEY: str = "change-me-in-production-32-chars!"
    API_PREFIX: str = "/api/v1"

    # --- Database ---
    DATABASE_URL: str = "postgresql+asyncpg://devbuddy:devbuddy@localhost:5432/devbuddy"

    # --- LLM Providers ---
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-20250514"
    LLAMA_API_KEY: str = ""
    LLAMA_MODEL: str = "llama-4-scout-17b-16e-instruct"
    LLAMA_API_BASE: str = "https://api.llama.com/v1"
    OLLAMA_API_KEY: str = ""
    OLLAMA_MODEL: str = "qwen3-coder:480b"
    OLLAMA_API_BASE: str = "https://ollama.com"

    # --- Token Budgets ---
    MAX_TOKENS_PER_REQUEST: int = 8192
    MAX_TOKENS_PER_TASK: int = 200_000
    COST_ALERT_THRESHOLD_USD: float = 5.0

    # --- Workspace ---
    WORKSPACE_ROOT: Path = Path("/tmp/devbuddy-workspaces")
    REPOS_ROOT: Path = Path("/tmp/devbuddy-repos")

    # --- GitHub ---
    GITHUB_TOKEN: str = ""
    GITHUB_DEFAULT_ORG: str = ""

    # --- Deployment ---
    RAILWAY_TOKEN: str = ""
    VERCEL_TOKEN: str = ""

    # --- Repair Loop ---
    MAX_REPAIR_RETRIES: int = 5

    # --- Auth ---
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 day
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD_HASH: str = ""  # set via env

    # --- Google OAuth ---
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/google/callback"
    # Where to send the user after Google login (e.g. https://devbuddy.org or https://dev.devbuddy.org)
    FRONTEND_URL: str = "https://sivasbrmni-devbuddy.hf.space"
    # Comma-separated list of allowed emails (empty = block all)
    ALLOWED_EMAILS: str = "sivasbrmni@gmail.com"

    @property
    def frontend_url(self) -> str:
        if self.FRONTEND_URL:
            return self.FRONTEND_URL.rstrip("/")
        # Fallback: derive from redirect URI (removes /api/v1/... path)
        return self.GOOGLE_REDIRECT_URI.split("/api/")[0].rstrip("/")

    @property
    def allowed_emails_set(self) -> set[str]:
        return {e.strip().lower() for e in self.ALLOWED_EMAILS.split(",") if e.strip()}


settings = Settings()
