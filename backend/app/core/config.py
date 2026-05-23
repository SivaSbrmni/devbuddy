from pydantic_settings import BaseSettings
from typing import Optional


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

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
