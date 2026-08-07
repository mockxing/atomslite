import os
from pathlib import Path
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_MODEL: str = "gpt-4o"
    # Railway: set DATABASE_URL=sqlite+aiosqlite:////data/atoms_lite.db + mount volume at /data
    DATABASE_URL: str = "sqlite+aiosqlite:///./atoms_lite.db"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    # Comma-separated list of allowed CORS origins (e.g. https://atoms-lite.vercel.app)
    CORS_ORIGINS: str = "*"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    settings = Settings()
    # Auto-create the data directory if DATABASE_URL points to /data/ (Railway volume)
    if "/data/" in settings.DATABASE_URL:
        Path("/data").mkdir(parents=True, exist_ok=True)
    return settings
