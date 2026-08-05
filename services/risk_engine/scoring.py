"""The Risk Scoring Engine.

Sums the results of every registered RiskFactor into a total score, maps
that score to a discrete RiskLevel via configured thresholds, and preserves
the full per-factor breakdown — this is what makes every score explainable
and reproducible (NFR-1): identical asset + signal inputs always produce
the identical score, level, and breakdown.
"""

from dataclasses import dataclass
from uuid import UUID

from models.asset import Asset
from models.enums import RiskLevel
from models.exposure_signal import ExposureSignal
from services.risk_engine.base import RiskFactor, RiskFactorResult
from services.risk_engine.thresholds import REQUIRED_LEVELS


@dataclass(frozen=True)
class RiskScoreResult:
    """The full outcome of scoring one asset.

    Attributes:
        asset_id: Which asset this score belongs to.
        total_score: Sum of every factor's weight_applied.
        risk_level: The discrete bucket total_score falls into.
        factor_results: The complete per-factor breakdown — every
            registered factor's result, triggered or not — so a caller
            can always answer "why this score?" without recomputing.
    """

    asset_id: UUID
    total_score: int
    risk_level: RiskLevel
    factor_results: list[RiskFactorResult]


class RiskScoringEngine:
    """Scores assets by evaluating every configured RiskFactor and mapping
    the total to a RiskLevel."""

    def __init__(self, factors: list[RiskFactor], thresholds: dict[RiskLevel, int]) -> None:
        """
        Args:
            factors: Factor instances to evaluate, typically from
                build_factors() (services/risk_engine/weights.py).
            thresholds: RiskLevel -> minimum score, typically from
                load_risk_thresholds() (services/risk_engine/thresholds.py).
                Must contain all four RiskLevel values.
        """
        missing = set(REQUIRED_LEVELS) - set(thresholds.keys())
        if missing:
            raise ValueError(
                f"thresholds must define every RiskLevel; missing: "
                f"{sorted(level.value for level in missing)}"
            )
        self._factors = factors
        self._thresholds = thresholds

    def score_asset(self, asset: Asset, exposure_signals: list[ExposureSignal]) -> RiskScoreResult:
        """Evaluate every factor against this asset and produce a full score."""
        factor_results = [factor.evaluate(asset, exposure_signals) for factor in self._factors]
        total_score = sum(result.weight_applied for result in factor_results)
        risk_level = self._score_to_level(total_score)

        return RiskScoreResult(
            asset_id=asset.id,
            total_score=total_score,
            risk_level=risk_level,
            factor_results=factor_results,
        )

    def _score_to_level(self, score: int) -> RiskLevel:
        """Map a numeric score to the highest RiskLevel whose threshold the
        score meets or exceeds. REQUIRED_LEVELS is ordered low->critical,
        so checking from the top down finds the correct (highest) bucket."""
        for level in reversed(REQUIRED_LEVELS):
            if score >= self._thresholds[level]:
                return level
        # Unreachable in practice: LOW's threshold is validated as the
        # smallest value, and scores are never negative (every factor's
        # weight_applied is non-negative), so LOW always matches at worst.
        return RiskLevel.LOW
