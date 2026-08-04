"""Unit tests for config.settings.Settings."""

from config.settings import Settings


def test_settings_load_defaults_when_no_env_file(monkeypatch, tmp_path):
    """With no .env and no overriding env vars, defaults should apply."""
    monkeypatch.chdir(tmp_path)  # no .env file exists here
    settings = Settings(_env_file=None)  # ignore any real .env during this test

    assert settings.environment == "development"
    assert settings.api_port == 8000
    assert settings.database_url.startswith("sqlite:///")


def test_settings_override_from_env_vars(monkeypatch):
    """Environment variables should override defaults."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("API_PORT", "9000")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@host/db")

    settings = Settings(_env_file=None)

    assert settings.environment == "production"
    assert settings.api_port == 9000
    assert settings.database_url == "postgresql://user:pass@host/db"


def test_settings_rejects_invalid_type(monkeypatch):
    """A non-integer API_PORT must raise a validation error, not silently coerce."""
    monkeypatch.setenv("API_PORT", "not-a-number")

    try:
        Settings(_env_file=None)
        raised = False
    except Exception:
        raised = True

    assert raised, "Expected Settings to reject a non-integer API_PORT"


def test_settings_env_file_example_matches_expected_keys():
    """.env.example should define every key Settings expects, so nothing
    is silently missing for a new developer copying it to .env."""
    with open(".env.example") as f:
        content = f.read()

    expected_keys = [
        "APP_NAME",
        "ENVIRONMENT",
        "DEBUG",
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
