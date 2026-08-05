"""The Confidence Scoring Engine.

Confidence measures how much to TRUST an asset's data — distinct from
RiskScoringEngine (services/risk_engine/scoring.py), which measures how
DANGEROUS the asset is if compromised. These are deliberately never
combined into one number: a low-confidence record on a critical asset
should prompt "go verify this," not silently inflate or deflate its risk
score.

Two independent inputs feed the final score:
  - Source reliability: how much to trust WHERE this record came from
    (manual entry is human-verified; automated discovery carries more
    uncertainty until Discovery Reconciliation, Milestone 16, matures).
  - Recency: how much to trust that the record still reflects reality,
    decaying the longer it's been since the asset was last confirmed seen.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from models.asset import Asset
from models.enums import DiscoverySource

MIN_SCORE = 0
MAX_SCORE = 100

DEFAULT_SOURCE_RELIABILITY: dict[DiscoverySource, int] = {
    DiscoverySource.MANUAL: 100,
    DiscoverySource.DISCOVERY_PROVIDER: 70,
}


@dataclass(frozen=True)
class ConfidenceScoreResult:
    """The full outcome of confidence-scoring one asset.

    Attributes:
        asset_id: Which asset this result belongs to.
        confidence_score: Final 0-100 score (average of the two components).
        source_reliability_score: The source-reliability component alone.
        recency_score: The recency component alone.
        reason: Human-readable explanation of both components, so a caller
            never has to recompute to understand "why this number".
    """

    asset_id: UUID
    confidence_score: int
    source_reliability_score: int
    recency_score: int
    reason: str


class ConfidenceScoringEngine:
    """Computes a 0-100 confidence score for an asset's data, independent
    of its risk score."""

    def __init__(
        self,
        staleness_threshold_days: int = 30,
        recency_floor: int = 20,
        source_reliability: dict[DiscoverySource, int] | None = None,
    ) -> None:
        """
        Args:
            staleness_threshold_days: Days since last_seen at which recency
                bottoms out at recency_floor. Deliberately reuses the same
                default as Asset.is_stale() for a consistent mental model
                of "stale", though the two are independent settings.
            recency_floor: The minimum recency score once fully stale (a
                very old record still carries some signal, never zero).
            source_reliability: DiscoverySource -> 0-100 reliability score.
                Must cover every DiscoverySource value. Defaults to
                DEFAULT_SOURCE_RELIABILITY.

        Raises:
            ValueError: if staleness_threshold_days isn't positive,
                recency_floor is outside [0, 100], any reliability score
                is outside [0, 100], or a DiscoverySource value is missing
                from source_reliability.
        """
        if staleness_threshold_days <= 0:
            raise ValueError(
                f"staleness_threshold_days must be positive, got {staleness_threshold_days}."
            )
        if not (MIN_SCORE <= recency_floor <= MAX_SCORE):
            raise ValueError(
                f"recency_floor must be between {MIN_SCORE} and {MAX_SCORE}, got {recency_floor}."
            )

        reliability: dict[DiscoverySource, int] = (
            dict(source_reliability)
            if source_reliability is not None
            else dict(DEFAULT_SOURCE_RELIABILITY)
        )
        all_sources = cast(set[DiscoverySource], set(DiscoverySource))
        missing: set[DiscoverySource] = all_sources - set(reliability.keys())
        if missing:
            raise ValueError(
                f"source_reliability is missing entries for: "
                f"{sorted(source.value for source in missing)}"
            )
        for source, score in reliability.items():
            if not (MIN_SCORE <= score <= MAX_SCORE):
                raise ValueError(
                    f"Reliability score for '{source.value}' must be between "
                    f"{MIN_SCORE} and {MAX_SCORE}, got {score}."
                )

        self._staleness_threshold_days = staleness_threshold_days
        self._recency_floor = recency_floor
        self._source_reliability = reliability

    def score_asset(self, asset: Asset) -> ConfidenceScoreResult:
        """Compute the confidence score for a single asset."""
        source_score = self._source_reliability[asset.discovery_source]
        recency_score = self._compute_recency_score(asset)
        confidence_score = round((source_score + recency_score) / 2)

        days_since_last_seen = (datetime.now(UTC) - asset.last_seen).days
        reason = (
            f"Source '{asset.discovery_source.value}' reliability: {source_score}/100. "
            f"{max(days_since_last_seen, 0)} day(s) since last seen, "
            f"recency: {recency_score}/100."
        )

        return ConfidenceScoreResult(
            asset_id=asset.id,
            confidence_score=confidence_score,
            source_reliability_score=source_score,
            recency_score=recency_score,
            reason=reason,
        )

    def _compute_recency_score(self, asset: Asset) -> int:
        """Linear decay from 100 (just seen) to recency_floor (at or beyond
        the staleness threshold). A last_seen timestamp in the future
        (clock skew, test data) is treated as "just seen" -> 100."""
        days_since_last_seen = (datetime.now(UTC) - asset.last_seen).days

        if days_since_last_seen <= 0:
            return MAX_SCORE
        if days_since_last_seen >= self._staleness_threshold_days:
            return self._recency_floor

        fraction_remaining = 1 - (days_since_last_seen / self._staleness_threshold_days)
        score = self._recency_floor + fraction_remaining * (MAX_SCORE - self._recency_floor)
        return round(score)
