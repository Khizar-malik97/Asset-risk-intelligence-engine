"""Cross-cutting search/filter service.

Combines the repository's fast, SQL-backed filters (category, criticality,
asset type, text) with two filters that can't be pushed down to a single
SQL query against the assets table:

  - exposure_signal_type: requires joining against the separate
    exposure_signals table/repository (Milestone 11).
  - risk_level: not stored anywhere — computed on the fly by
    RiskScoringEngine (Milestone 13) from an asset's factors, so filtering
    by it means scoring every DB-filtered candidate in Python.

Kept as its own service (not folded into InventoryService) since it reads
across three collaborators (asset repository, exposure signal repository,
optionally the risk scoring engine) rather than owning a single table's
lifecycle.
"""

from models.asset import Asset
from models.enums import AssetCategory, AssetType, RiskLevel
from models.exposure_signal import ExposureSignalType
from repositories.exposure_signal_repository import ExposureSignalRepositoryInterface
from repositories.interfaces import AssetRepositoryInterface
from services.risk_engine.scoring import RiskScoringEngine
from utils.exceptions import InvalidRequestError


class AssetSearchService:
    """Combined search/filter over the asset inventory."""

    def __init__(
        self,
        asset_repository: AssetRepositoryInterface,
        exposure_signal_repository: ExposureSignalRepositoryInterface,
        risk_scoring_engine: RiskScoringEngine | None = None,
    ) -> None:
        """
        Args:
            asset_repository: source of DB-backed filtering (search()).
            exposure_signal_repository: source of per-asset exposure signals,
                needed for exposure_signal_type filtering and, if used,
                risk_level filtering.
            risk_scoring_engine: required only if callers filter by
                risk_level; omit if that filter will never be used (e.g. in
                a context that hasn't wired up risk config yet).
        """
        self._asset_repository = asset_repository
        self._exposure_signal_repository = exposure_signal_repository
        self._risk_scoring_engine = risk_scoring_engine

    def search(
        self,
        *,
        category: AssetCategory | None = None,
        is_critical: bool | None = None,
        asset_type: AssetType | None = None,
        text: str | None = None,
        exposure_signal_type: ExposureSignalType | None = None,
        risk_level: RiskLevel | None = None,
    ) -> list[Asset]:
        """Return assets matching every provided filter (AND semantics).

        Filter evaluation order is deliberate: cheapest/most-selective
        (DB-backed) filters run first to shrink the candidate set before
        the more expensive exposure-signal and risk-scoring passes run
        only against what's left.

        Raises:
            ValueError: if risk_level is given but no RiskScoringEngine was
                provided at construction time.
        """
        candidates = self._asset_repository.search(
            category=category,
            is_critical=is_critical,
            asset_type=asset_type,
            text=text,
        )

        if exposure_signal_type is not None:
            candidates = [
                asset for asset in candidates if self._has_signal_type(asset, exposure_signal_type)
            ]

        if risk_level is not None:
            if self._risk_scoring_engine is None:
                raise InvalidRequestError(
                    "risk_level filtering requires a RiskScoringEngine to be "
                    "configured on AssetSearchService.",
                    details={"filter": "risk_level"},
                )
            candidates = [
                asset for asset in candidates if self._matches_risk_level(asset, risk_level)
            ]

        return candidates

    def _has_signal_type(self, asset: Asset, signal_type: ExposureSignalType) -> bool:
        signals = self._exposure_signal_repository.list_for_asset(asset.id)
        return any(signal.signal_type == signal_type for signal in signals)

    def _matches_risk_level(self, asset: Asset, risk_level: RiskLevel) -> bool:
        assert self._risk_scoring_engine is not None  # guarded by caller above
        signals = self._exposure_signal_repository.list_for_asset(asset.id)
        result = self._risk_scoring_engine.score_asset(asset, signals)
        return result.risk_level == risk_level
