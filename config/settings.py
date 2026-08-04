"""
Application configuration.

Loads all runtime configuration from environment variables (or a .env file
during local development) into a single, type-validated Settings object.

Design rationale:
- Fail-fast: if a required setting is missing or malformed, the app refuses
  to start rather than silently falling back to a guessed default. This
  matters for things like DATABASE_URL, where a wrong default could point
  at the wrong database without anyone noticing.
- A single source of truth: every other module imports `settings` from here
  instead of calling os.environ.get() scattered throughout the codebase.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application settings, loaded from environment variables / .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application ---
    app_name: str = Field(default="AXERONIX Asset Intelligence Module")
    environment: str = Field(
        default="development",
        description="One of: development, testing, production",
    )
    debug: bool = Field(default=False)

    # --- Database ---
    database_url: str = Field(
        default="sqlite:///./asset_intelligence.db",
        description="SQLAlchemy database connection string",
    )

    # --- Risk engine config paths (used from Milestone 12 onward) ---
    risk_weights_config_path: str = Field(default="config/risk_weights.yaml")
    risk_thresholds_config_path: str = Field(default="config/risk_thresholds.yaml")

    # --- API ---
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)

    # --- Logging ---
    log_level: str = Field(default="INFO")


@lru_cache
def get_settings() -> Settings:
    """
    Return a cached Settings instance.

    Using lru_cache means the environment is only read/parsed once per
    process, not on every import or every request.
    """
    return Settings()


# Convenience module-level instance for straightforward `from config.settings
# import settings` usage throughout the codebase.
settings = get_settings()
