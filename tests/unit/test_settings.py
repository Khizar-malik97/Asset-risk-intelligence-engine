"""Unit tests for config.settings.Settings."""

import pytest
from pydantic import ValidationError

from config.settings import Settings


def test_settings_load_defaults_when_no_env_file(monkeypatch, tmp_path):
    """With no .env and no overriding env vars, defaults should apply
    (SECRET_KEY still has to come from somewhere — conftest.py provides it)."""
    monkeypatch.chdir(tmp_path)  # no .env file exists here
    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.environment == "development"
    assert settings.api_port == 8000
    assert settings.database_url.startswith("sqlite:///")


def test_settings_override_from_env_vars(monkeypatch):
    """Environment variables should override defaults."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("API_PORT", "9000")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@host/db")

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.environment == "production"
    assert settings.api_port == 9000
    assert settings.database_url == "postgresql://user:pass@host/db"


def test_settings_rejects_invalid_type(monkeypatch):
    """A non-integer API_PORT must raise a validation error, not silently coerce."""
    monkeypatch.setenv("API_PORT", "not-a-number")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_settings_requires_secret_key(monkeypatch):
    """SECRET_KEY has no default — omitting it must raise a clear validation
    error, not start the app with a missing/guessed secret. This is the
    Milestone 3 'missing required var' test called for in the roadmap."""
    monkeypatch.delenv("SECRET_KEY", raising=False)

    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)  # type: ignore[call-arg]

    assert "secret_key" in str(exc_info.value).lower()


def test_settings_rejects_too_short_secret_key(monkeypatch):
    """A SECRET_KEY shorter than 16 characters should be rejected, not
    silently accepted as a weak secret."""
    monkeypatch.setenv("SECRET_KEY", "tooshort")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_settings_env_file_example_matches_expected_keys():
    """.env.example should define every key Settings expects, so nothing
    is silently missing for a new developer copying it to .env."""
    with open(".env.example") as f:
        content = f.read()

    expected_keys = [
        "APP_NAME",
        "ENVIRONMENT",
        "DEBUG",
        "SECRET_KEY",
        "DATABASE_URL",
        "RISK_WEIGHTS_CONFIG_PATH",
        "RISK_THRESHOLDS_CONFIG_PATH",
        "API_HOST",
        "API_PORT",
        "LOG_LEVEL",
    ]
    for key in expected_keys:
        assert key in content, f"{key} missing from .env.example"


def test_get_settings_is_cached():
    """get_settings() should return the same cached instance on repeated calls."""
    from config.settings import get_settings

    first = get_settings()
    second = get_settings()
    assert first is second
