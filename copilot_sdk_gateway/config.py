"""Application configuration via pydantic-settings (12-factor)."""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """All configuration from environment variables."""

    port: int = 11434
    github_token: str = ""
    copilot_cli_path: str = ""
    copilot_cli_url: str = ""
    log_level: str = "error"
    inference_timeout: float = 300.0

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
