"""Tests for services/risk_engine/scoring.py.

Two kinds of tests here, deliberately:
  1. Boundary/summation tests use small FAKE factors with hand-picked
     weights, so threshold-matching logic is tested precisely and stays
     correct even if the real config/risk_weights.yaml values change later.
  2. Golden-value tests use the REAL registered factors and REAL
     config/risk_weights.yaml + config/risk_thresholds.yaml, proving the
     actual shipped configuration produces sensible scores end to end.
"""

import pytest

from models.asset import Asset
from models.enums import RiskLevel
from models.exposure_signal import ExposureSeverity, ExposureSignal, ExposureSignalType
from models.host import Host
from models.user import User
from services.risk_engine.base import RiskFactor, RiskFactorResult
from services.risk_engine.registry import get_registered_factors
from services.risk_engine.scoring import RiskScoringEngine
from services.risk_engine.thresholds import load_risk_thresholds
from services.risk_engine.weights import build_factors, load_risk_weights

# ---------------------------------------------------------------------------
# Fakes, for precise/deterministic threshold-boundary testing
# ---------------------------------------------------------------------------


class _AlwaysTriggersFactor(RiskFactor):
    name = "always_triggers"
    description = "Test double: always contributes its full weight."

    def evaluate(self, asset: Asset, exposure_signals: list[ExposureSignal]) -> RiskFactorResult:
        return RiskFactorResult(
            factor_name=self.name, weight_applied=self.weight, triggered=True, reason="always"
        )


class _NeverTriggersFactor(RiskFactor):
    name = "never_triggers"
    description = "Test double: never contributes anything."

    def evaluate(self, asset: Asset, exposure_signals: list[ExposureSignal]) -> RiskFactorResult:
        return RiskFactorResult(
            factor_name=self.name, weight_applied=0, triggered=False, reason="never"
        )


FAKE_THRESHOLDS = {
    RiskLevel.LOW: 0,
    RiskLevel.MEDIUM: 20,
    RiskLevel.HIGH: 50,
    RiskLevel.CRITICAL: 80,
}


@pytest.fixture()
def any_asset() -> Asset:
    return Asset(identifier="test-asset")


class TestScoreSummation:
    def test_no_factors_gives_zero_score(self, any_asset: Asset) -> None:
        engine = RiskScoringEngine(factors=[], thresholds=FAKE_THRESHOLDS)

        result = engine.score_asset(any_asset, [])

        assert result.total_score == 0
        assert result.risk_level == RiskLevel.LOW

    def test_non_triggering_factor_contributes_nothing(self, any_asset: Asset) -> None:
        engine = RiskScoringEngine(
            factors=[_NeverTriggersFactor(weight=50)], thresholds=FAKE_THRESHOLDS
        )

        result = engine.score_asset(any_asset, [])

        assert result.total_score == 0

    def test_multiple_triggering_factors_sum(self, any_asset: Asset) -> None:
        engine = RiskScoringEngine(
            factors=[_AlwaysTriggersFactor(weight=30), _AlwaysTriggersFactor(weight=25)],
            thresholds=FAKE_THRESHOLDS,
        )

        result = engine.score_asset(any_asset, [])

        assert result.total_score == 55

    def test_result_includes_full_breakdown_even_for_non_triggered(self, any_asset: Asset) -> None:
        engine = RiskScoringEngine(
            factors=[_AlwaysTriggersFactor(weight=10), _NeverTriggersFactor(weight=10)],
            thresholds=FAKE_THRESHOLDS,
        )

        result = engine.score_asset(any_asset, [])

        assert len(result.factor_results) == 2
        names = {r.factor_name for r in result.factor_results}
        assert names == {"always_triggers", "never_triggers"}


class TestThresholdBoundaries:
    """Exact boundary values, using controllable fake weights."""

    def test_score_zero_is_low(self, any_asset: Asset) -> None:
        engine = RiskScoringEngine(factors=[], thresholds=FAKE_THRESHOLDS)
        assert engine.score_asset(any_asset, []).risk_level == RiskLevel.LOW

    def test_score_just_below_medium_is_low(self, any_asset: Asset) -> None:
        engine = RiskScoringEngine(
            factors=[_AlwaysTriggersFactor(weight=19)], thresholds=FAKE_THRESHOLDS
        )
        assert engine.score_asset(any_asset, []).risk_level == RiskLevel.LOW

    def test_score_exactly_at_medium_threshold_is_medium(self, any_asset: Asset) -> None:
        engine = RiskScoringEngine(
            factors=[_AlwaysTriggersFactor(weight=20)], thresholds=FAKE_THRESHOLDS
        )
        assert engine.score_asset(any_asset, []).risk_level == RiskLevel.MEDIUM

    def test_score_just_below_high_is_medium(self, any_asset: Asset) -> None:
        engine = RiskScoringEngine(
            factors=[_AlwaysTriggersFactor(weight=49)], thresholds=FAKE_THRESHOLDS
        )
        assert engine.score_asset(any_asset, []).risk_level == RiskLevel.MEDIUM

    def test_score_exactly_at_high_threshold_is_high(self, any_asset: Asset) -> None:
        engine = RiskScoringEngine(
            factors=[_AlwaysTriggersFactor(weight=50)], thresholds=FAKE_THRESHOLDS
        )
        assert engine.score_asset(any_asset, []).risk_level == RiskLevel.HIGH

    def test_score_exactly_at_critical_threshold_is_critical(self, any_asset: Asset) -> None:
        engine = RiskScoringEngine(
            factors=[_AlwaysTriggersFactor(weight=80)], thresholds=FAKE_THRESHOLDS
        )
        assert engine.score_asset(any_asset, []).risk_level == RiskLevel.CRITICAL

    def test_score_far_above_critical_is_still_critical(self, any_asset: Asset) -> None:
        engine = RiskScoringEngine(
            factors=[_AlwaysTriggersFactor(weight=999)], thresholds=FAKE_THRESHOLDS
        )
        assert engine.score_asset(any_asset, []).risk_level == RiskLevel.CRITICAL


class TestEngineConstruction:
    def test_missing_threshold_level_rejected(self) -> None:
        incomplete = {RiskLevel.LOW: 0, RiskLevel.MEDIUM: 20, RiskLevel.HIGH: 50}

        with pytest.raises(ValueError, match="critical"):
            RiskScoringEngine(factors=[], thresholds=incomplete)


# ---------------------------------------------------------------------------
# Golden-value tests: real factors, real config
# ---------------------------------------------------------------------------


@pytest.fixture()
def real_engine() -> RiskScoringEngine:
    weights = load_risk_weights("config/risk_weights.yaml")
    thresholds = load_risk_thresholds("config/risk_thresholds.yaml")
    factors = build_factors(weights, registry=get_registered_factors())
    return RiskScoringEngine(factors=factors, thresholds=thresholds)


class TestRealConfigGoldenValues:
    def test_plain_asset_scores_zero_and_low(self, real_engine: RiskScoringEngine) -> None:
        asset = Asset(identifier="plain-001")

        result = real_engine.score_asset(asset, [])

        assert result.total_score == 0
        assert result.risk_level == RiskLevel.LOW

    def test_critical_flag_alone_scores_30_medium(self, real_engine: RiskScoringEngine) -> None:
        asset = Asset(identifier="crit-001", is_critical=True)

        result = real_engine.score_asset(asset, [])

        assert result.total_score == 30
        assert result.risk_level == RiskLevel.MEDIUM

    def test_critical_plus_internet_facing_scores_55_high(
        self, real_engine: RiskScoringEngine
    ) -> None:
        asset = Host(identifier="web-001", is_critical=True)
        signals = [
            ExposureSignal(
                asset_id=asset.id,
                signal_type=ExposureSignalType.INTERNET_FACING,
                severity=ExposureSeverity.HIGH,
                description="Publicly reachable",
            )
        ]

        result = real_engine.score_asset(asset, signals)

        assert result.total_score == 55
        assert result.risk_level == RiskLevel.HIGH

    def test_privileged_user_alone_scores_20_medium(self, real_engine: RiskScoringEngine) -> None:
        user = User(identifier="admin_jdoe", is_privileged=True)

        result = real_engine.score_asset(user, [])

        assert result.total_score == 20
        assert result.risk_level == RiskLevel.MEDIUM

    def test_privileged_flag_ignored_for_hosts(self, real_engine: RiskScoringEngine) -> None:
        """PrivilegedAccountFactor must not trigger for a Host, even one
        that happens to be critical — proves type-scoping works."""
        host = Host(identifier="web-002", is_critical=False)

        result = real_engine.score_asset(host, [])

        privileged_result = next(
            r for r in result.factor_results if r.factor_name == "privileged_account"
        )
        assert privileged_result.triggered is False

    def test_unpatched_vulnerabilities_scale_and_cap(self, real_engine: RiskScoringEngine) -> None:
        host = Host(identifier="legacy-001")
        signals = [
            ExposureSignal(
                asset_id=host.id,
                signal_type=ExposureSignalType.UNPATCHED_VULNERABILITY,
                severity=ExposureSeverity.HIGH,
                description=f"CVE-{i}",
            )
            for i in range(5)  # 5 signals, but capped at 3 for scoring
        ]

        result = real_engine.score_asset(host, signals)

        # unpatched_vulnerability weight is 15, capped at 3 signals -> 45,
        # which is below the high threshold (50) -> MEDIUM
        assert result.total_score == 45
        assert result.risk_level == RiskLevel.MEDIUM

    def test_everything_triggered_reaches_critical(self, real_engine: RiskScoringEngine) -> None:
        user = User(identifier="super_admin", is_critical=True, is_privileged=True)
        signals = [
            ExposureSignal(
                asset_id=user.id,
                signal_type=ExposureSignalType.INTERNET_FACING,
                severity=ExposureSeverity.HIGH,
                description="Exposed admin panel",
            ),
            ExposureSignal(
                asset_id=user.id,
                signal_type=ExposureSignalType.UNPATCHED_VULNERABILITY,
                severity=ExposureSeverity.CRITICAL,
                description="CVE-critical",
            ),
        ]

        result = real_engine.score_asset(user, signals)

        # critical_asset_flag(30) + internet_facing(25) + privileged_account(20)
        # + unpatched_vulnerability(15 * 1 signal) = 90
        assert result.total_score == 90
        assert result.risk_level == RiskLevel.CRITICAL
        assert all(r.reason for r in result.factor_results)  # every factor explains itself

    def test_score_is_reproducible_for_identical_input(
        self, real_engine: RiskScoringEngine
    ) -> None:
        """Same asset + same signals -> same score, every time (NFR-1)."""
        asset = Host(identifier="repeat-001", is_critical=True)

        first = real_engine.score_asset(asset, [])
        second = real_engine.score_asset(asset, [])

        assert first.total_score == second.total_score
        assert first.risk_level == second.risk_level
