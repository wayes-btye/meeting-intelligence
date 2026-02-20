from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings validated via Pydantic.

    Values are loaded from environment variables and/or a .env file.
    """

    # API Keys
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    assemblyai_api_key: str = ""
    gemini_api_key: str = ""  # Optional — Gemini visual summary; graceful degradation if absent

    # Supabase
    supabase_url: str = ""
    supabase_key: str = ""

    # App config
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    llm_model: str = "claude-sonnet-4-20250514"
    chunk_size: int = 500
    chunk_overlap: int = 50

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance.

    Gracefully handles missing .env files (e.g. in CI/testing) by falling
    back to environment variables and defaults.
    """
    try:
        return Settings()
    except Exception:
        # If .env is missing or unreadable, build settings from env vars only.
        return Settings(_env_file=None)  # type: ignore[call-arg]


settings = get_settings()
