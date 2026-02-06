"""Configuration via environment variables."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings

_PROJECT_ROOT = Path(__file__).parent.parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """YouLearn configuration."""

    # OpenRouter
    openrouter_api_key: str = ""
    openrouter_model: str = "openai/gpt-4o-mini"

    # Workspace — where the agent reads/writes files
    workspace: str = str(Path(__file__).parent.parent.parent.parent / "classes")

    # Server
    host: str = "0.0.0.0"
    port: int = 8200

    model_config = {"env_prefix": "YOULEARN_", "env_file": _ENV_FILE}


@lru_cache
def get_settings() -> Settings:
    """Get settings singleton."""
    return Settings()
