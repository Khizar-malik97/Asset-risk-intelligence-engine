"""Unit tests for services/risk_engine/confidence.py."""

from datetime import UTC, datetime, timedelta

import pytest

from models.asset import Asset
from models.enums import DiscoverySource
from services.risk_engine.confidence import ConfidenceScoringEngine


def _asset_seen_days_ago(days: int, source: DiscoverySource = DiscoverySource.MANUAL) -> Asset:
    asset = Asset(identifier="test-asset", discovery_source=source)
    asset.last_seen = datetime.now(UTC) - timedelta(days=days)
    return asset


class TestRecencyDecay:
    """staleness_threshold_days=30, recency_floor=20 (defaults) throughout."""

    def test_just_seen_scores_full_recency(self) -> None:
        engine = ConfidenceScoringEngine()
        asset = _asset_seen_days_ago(0)

        result = engine.score_asset(asset)

        assert result.recency_score == 100

    def test_future_last_seen_scores_full_recency(self) -> None:
        """Clock skew / test data edge case: last_seen in the future should
        not produce a negative day count or crash — treated as "just seen"."""
        engine = ConfidenceScoringEngine()
        asset = Asset(identifier="future-asset")
        asset.last_seen = datetime.now(UTC) + timedelta(days=5)

        result = engine.score_asset(asset)

        assert result.recency_score == 100

    def test_halfway_to_threshold_is_interpolated(self) -> None:
        # 15 days of 30 -> fraction_remaining=0.5 -> 20 + 0.5*(100-20) = 60
        engine = ConfidenceScoringEngine(staleness_threshold_days=30, recency_floor=20)
        asset = _asset_seen_days_ago(15)

        result = engine.score_asset(asset)

        assert result.recency_score == 60

    def test_exactly_at_threshold_hits_floor(self) -> None:
        engine = ConfidenceScoringEngine(staleness_threshold_days=30, recency_floor=20)
        asset = _asset_seen_days_ago(30)

        result = engine.score_asset(asset)

        assert result.recency_score == 20

    def test_far_past_threshold_stays_at_floor(self) -> None:
        engine = ConfidenceScoringEngine(staleness_threshold_days=30, recency_floor=20)
        asset = _asset_seen_days_ago(365)

        result = engine.score_asset(asset)

        assert result.recency_score == 20

    def test_custom_floor_is_respected(self) -> None:
        engine = ConfidenceScoringEngine(staleness_threshold_days=10, recency_floor=0)
        asset = _asset_seen_days_ago(10)

        result = engine.score_asset(asset)

        assert result.recency_score == 0


class TestSourceReliability:
    def test_manual_source_uses_default_reliability(self) -> None:
        engine = ConfidenceScoringEngine()
        asset = _asset_seen_days_ago(0, source=DiscoverySource.MANUAL)

        result = engine.score_asset(asset)

        assert result.source_reliability_score == 100

    def test_discovery_provider_source_uses_default_reliability(self) -> None:
        engine = ConfidenceScoringEngine()
        asset = _asset_seen_days_ago(0, source=DiscoverySource.DISCOVERY_PROVIDER)

        result = engine.score_asset(asset)

        assert result.source_reliability_score == 70

    def test_custom_reliability_mapping_is_used(self) -> None:
        engine = ConfidenceScoringEngine(
            source_reliability={
                DiscoverySource.MANUAL: 90,
                DiscoverySource.DISCOVERY_PROVIDER: 40,
            }
        )
        asset = _asset_seen_days_ago(0, source=DiscoverySource.DISCOVERY_PROVIDER)

        result = engine.score_asset(asset)

        assert result.source_reliability_score == 40


class TestCombinedScore:
    def test_confidence_is_average_of_components(self) -> None:
        # manual (100) + just-seen (100) -> average 100
        engine = ConfidenceScoringEngine()
        asset = _asset_seen_days_ago(0, source=DiscoverySource.MANUAL)

        result = engine.score_asset(asset)

        assert result.confidence_score == 100

    def test_stale_discovery_provider_asset_scores_low(self) -> None:
        # discovery_provider (70) + fully stale (20) -> average 45
        engine = ConfidenceScoringEngine()
        asset = _asset_seen_days_ago(365, source=DiscoverySource.DISCOVERY_PROVIDER)

        result = engine.score_asset(asset)

        assert result.confidence_score == 45

    def test_reason_mentions_both_components(self) -> None:
        engine = ConfidenceScoringEngine()
        asset = _asset_seen_days_ago(0, source=DiscoverySource.MANUAL)

        result = engine.score_asset(asset)

        assert "manual" in result.reason
        assert "recency" in result.reason.lower()

    def test_score_is_reproducible_for_identical_input(self) -> None:
        engine = ConfidenceScoringEngine()
        asset = _asset_seen_days_ago(10)

        first = engine.score_asset(asset)
        second = engine.score_asset(asset)

        assert first.confidence_score == second.confidence_score


class TestEngineConstruction:
    def test_zero_staleness_threshold_rejected(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            ConfidenceScoringEngine(staleness_threshold_days=0)

    def test_negative_staleness_threshold_rejected(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            ConfidenceScoringEngine(staleness_threshold_days=-5)

    def test_recency_floor_above_100_rejected(self) -> None:
        with pytest.raises(ValueError, match="recency_floor"):
            ConfidenceScoringEngine(recency_floor=101)

    def test_recency_floor_below_0_rejected(self) -> None:
        with pytest.raises(ValueError, match="recency_floor"):
            ConfidenceScoringEngine(recency_floor=-1)

    def test_incomplete_source_reliability_mapping_rejected(self) -> None:
        with pytest.raises(ValueError, match="missing"):
            ConfidenceScoringEngine(source_reliability={DiscoverySource.MANUAL: 100})

    def test_out_of_range_reliability_score_rejected(self) -> None:
        with pytest.raises(ValueError, match="between"):
            ConfidenceScoringEngine(
                source_reliability={
                    DiscoverySource.MANUAL: 150,
                    DiscoverySource.DISCOVERY_PROVIDER: 70,
                }
            )
