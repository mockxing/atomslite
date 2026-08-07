import os
import json
import logging
from pathlib import Path
from pydantic_settings import BaseSettings
from functools import lru_cache

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_MODEL: str = "gpt-4o"
    # Multi-model failover pool. JSON array of providers:
    # [{"key":"sk-xxx","base_url":"https://...","model":"gemini-2.5-flash"},
    #  {"key":"sk-yyy","base_url":"https://...","model":"kimi-k2.7-code"}]
    # When set, overrides OPENAI_API_KEY/BASE_URL/MODEL. Each provider is tried
    # in order; on 503/429/timeout/connection error it falls back to the next.
    MODEL_POOL: str = ""
    # Railway production: set DATABASE_URL=sqlite+aiosqlite:////data/atoms_lite.db
    # AND mount a persistent volume at /data, otherwise the SQLite DB is wiped on every redeploy.
    DATABASE_URL: str = "sqlite+aiosqlite:///./atoms_lite.db"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    # REQUIRED in production. Comma-separated allowed origins, e.g.
    # https://atoms-lite.vercel.app . Leave empty locally; MUST be set on deploy.
    CORS_ORIGINS: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        # Ignore any extra env vars / .env keys not declared above. Without this,
        # an unrelated variable (e.g. MODEL_POOL) in .env or the deployment env
        # makes Settings() fail and the whole app refuse to start.
        extra = "ignore"

    @property
    def model_pool(self) -> list[dict]:
        """Parse MODEL_POOL env var into a list of provider dicts.

        Returns [] if not set or invalid. Falls back to single OPENAI_* config
        when MODEL_POOL is empty.
        """
        if not self.MODEL_POOL:
            return []
        raw = self.MODEL_POOL.strip()
        # Auto-fix full-width comma (common in CJK input). Do NOT touch slashes —
        # replace("https:/","https://") would corrupt valid "https://" into "https:///".
        raw = raw.replace("\uff0c", ",")
        try:
            pool = json.loads(raw)
            if isinstance(pool, list) and pool:
                return pool
            if isinstance(pool, list) and not pool:
                return []
        except (json.JSONDecodeError, TypeError) as e:
            logger.error("MODEL_POOL parse failed: %s | raw: %s", e, raw[:200])
        return []


@lru_cache()
def get_settings() -> Settings:
    settings = Settings()
    # Auto-create the data directory if DATABASE_URL points to /data/ (Railway volume)
    if "/data/" in settings.DATABASE_URL:
        Path("/data").mkdir(parents=True, exist_ok=True)
    return settings
