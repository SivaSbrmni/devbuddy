from pydantic_settings import BaseSettings
from typing import Optional, Literal


class Settings(BaseSettings):
    APP_NAME: str = "DevBuddy Enterprise Agent Platform"
    ENVIRONMENT: str = "development"
    SECRET_KEY: str = "change-me"

    DATABASE_URL: str
    DATABASE_URL_SYNC: str = ""

    SUPABASE_URL: str = "https://placeholder.supabase.co"
    SUPABASE_ANON_KEY: str = "placeholder"
    SUPABASE_JWT_SECRET: str = "dev-local-secret-change-in-production-min32chars!"

    LOKI_URL: str = "http://loki:3100"

    # ── LLM provider config ──────────────────────────────────────────────────
    # LLM_PROVIDER: "ollama" (local) | "openai" | "groq" | "together" | "custom"
    # For "ollama" → uses OLLAMA_URL, no key needed
    # For others   → uses LLM_API_BASE + LLM_API_KEY (OpenAI-compatible)
    LLM_PROVIDER: Literal["ollama", "openai", "groq", "together", "custom"] = "ollama"
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
            "custom":   "",
        }.get(self.LLM_PROVIDER, "")

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
