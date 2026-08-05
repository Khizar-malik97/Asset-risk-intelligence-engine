"""
Shared pytest configuration.

`config/settings.py` builds a module-level `settings` singleton at import
time, and `secret_key` is a required field with no default (by design — see
the docstring in settings.py). That means simply *importing* config.settings
anywhere — including from a test file — will raise a validation error unless
SECRET_KEY is already set in the environment before that import happens.

This conftest sets a safe, obviously-fake test value as early as possible
(conftest.py is loaded by pytest before it imports any test modules), so the
test suite works the same whether or not a developer has a local .env file
with their own SECRET_KEY set.
"""

import os

os.environ.setdefault("SECRET_KEY", "test-secret-key-do-not-use-in-production")
