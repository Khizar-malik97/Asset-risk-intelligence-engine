"""Unit tests for utils/datetime_utils.py."""

from datetime import UTC, datetime, timedelta, timezone

from utils.datetime_utils import ensure_utc


class TestEnsureUtc:
    def test_naive_datetime_gets_utc_attached(self):
        naive = datetime(2026, 1, 15, 10, 30, 0)

        result = ensure_utc(naive)

        assert result.tzinfo == UTC
        # The wall-clock value itself must not change — only tzinfo is added.
        assert result.replace(tzinfo=None) == naive

    def test_already_utc_datetime_is_unchanged(self):
        aware = datetime(2026, 1, 15, 10, 30, 0, tzinfo=UTC)

        result = ensure_utc(aware)

        assert result == aware
        assert result.tzinfo == UTC

    def test_non_utc_aware_datetime_is_not_reinterpreted(self):
        """A timestamp that already has a real (non-UTC) timezone must be
        returned exactly as-is — never silently relabeled as UTC."""
        other_tz = timezone(timedelta(hours=5))
        aware = datetime(2026, 1, 15, 10, 30, 0, tzinfo=other_tz)

        result = ensure_utc(aware)

        assert result == aware
        assert result.tzinfo == other_tz

    def test_result_is_usable_in_aware_arithmetic(self):
        """The actual bug this helper fixes: a naive datetime straight from
        SQLite must become usable in arithmetic against datetime.now(UTC)
        without raising TypeError."""
        naive = datetime(2020, 1, 1, 0, 0, 0)

        result = ensure_utc(naive)

        # Should not raise "can't subtract offset-naive and offset-aware datetimes"
        delta = datetime.now(UTC) - result
        assert delta.days > 0
