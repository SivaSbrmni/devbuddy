"""
Configuration — environment variables.

Supabase Postgres (recommended for production):
  DATABASE_URL=postgresql+asyncpg://postgres:PASSWORD@db.REF.supabase.co:5432/postgres
  Or use the connection pooler for serverless:
  DATABASE_URL=postgresql+asyncpg://postgres.REF:PASSWORD@aws-0-us-west-1.pooler.supabase.com:6543/postgres

For local dev:
  DATABASE_URL=postgresql+asyncpg://devbuddy:devbuddy@localhost:5432/devbuddy

Note: Supabase already has pgvector enabled by default.
"""
from pydantic_settings import BaseSettings
from typing import Optional, Literal


class Settings(BaseSettings):
    APP_NAME: str = "DevBuddy Enterprise Agent Platform"
    ENVIRONMENT: str = "development"
    SECRET_KEY: str = "change-me"

    # Supabase Postgres (or any Postgres). Use the pooler URL for serverless/Fly.io
    # Example: postgresql+asyncpg://postgres.PID:PASS@aws-0-region.pooler.supabase.com:6543/postgres
    DATABASE_URL: str
    DATABASE_URL_SYNC: str = ""  # Optional sync fallback for migrations

    SUPABASE_URL: str = "https://placeholder.supabase.co"
    SUPABASE_ANON_KEY: str = "placeholder"
    SUPABASE_JWT_SECRET: str = "dev-local-secret-change-in-production-min32chars!"

    # pgvector is assumed available (Supabase includes it). For self-hosted, run:
    # CREATE EXTENSION IF NOT EXISTS vector;

    LOKI_URL: str = "http://loki:3100"

    # ── LLM provider config ──────────────────────────────────────────────────
    # LLM_PROVIDER: "ollama" (local) | "openai" | "groq" | "together" | "custom"
    # For "ollama" → uses OLLAMA_URL, no key needed
    # For others   → uses LLM_API_BASE + LLM_API_KEY (OpenAI-compatible)
    LLM_PROVIDER: Literal["ollama", "openai", "groq", "together", "llama", "custom"] = "ollama"
    LLM_MODEL: str = "llama3.2:latest"
    LLM_API_KEY: Optional[str] = None

    # Ollama-specific
    OLLAMA_URL: str = "http://host.docker.internal:11434"

    # OpenAI-compatible base URLs
    LLM_API_BASE: Optional[str] = None  # override; defaults per provider below

    # Embedding model — used by memory_store.py
    # Ollama: "nomic-embed-text" (default)
    # OpenAI: "text-embedding-3-small"
    # Together: "togethercomputer/m2-bert-80M-8k-retrieval"
    # Leave empty to use provider defaults
    EMBED_MODEL: Optional[str] = None

    @property
    def resolved_api_base(self) -> str:
        if self.LLM_API_BASE:
            return self.LLM_API_BASE
        return {
            "ollama":   f"{self.OLLAMA_URL}/v1",
            "openai":   "https://api.openai.com/v1",
            "groq":     "https://api.groq.com/openai/v1",
            "together": "https://api.together.xyz/v1",
            "llama":    "https://api.llama.com/compat/v1",
            "custom":   "",
        }.get(self.LLM_PROVIDER, "")

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
