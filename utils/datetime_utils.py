"""Shared datetime helpers.

SQLite has no real timezone-aware datetime type: regardless of how a
column is declared (Mapped[datetime], DateTime(timezone=True), etc.),
every value round-tripped through SQLite comes back as a naive datetime.
Every domain model in this codebase always writes UTC-aware datetimes
(datetime.now(UTC) — see models/asset.py, models/exposure_signal.py), so
a naive datetime coming back from persistence is safe to assume as UTC.

This is the one place that assumption is made explicit, so every
repository's mapper reuses it instead of each guessing independently (or
worse, each repository silently producing objects with a different,
inconsistent timezone-awareness depending on whether the data just came
from the DB or was freshly constructed in Python).
"""

from datetime import UTC, datetime


def ensure_utc(value: datetime) -> datetime:
    """Return a UTC-aware version of `value`.

    If `value` is already timezone-aware, it's returned unchanged — never
    reinterpret a timestamp that already carries correct tzinfo. If it's
    naive (e.g. just loaded from SQLite), UTC is attached, per the
    assumption documented above.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
