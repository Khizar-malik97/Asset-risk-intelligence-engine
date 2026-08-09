"""Read-only integration context service (Milestone 26).

Deliberately thin — it composes AssetInventoryService, ExposureSignalService,
RiskScoringEngine, and ConfidenceScoringEngine (all built in earlier
milestones) into the lean AssetContext shape other modules consume. It adds
no new business logic of its own; the actual scoring rules live exactly
where they already did.
"""

from collections import Counter
from uuid import UUID

from models.asset import Asset
from models.enums import RiskLevel
from schemas.integration import (
    AssetContext,
    BulkContextResponse,
    CategoryCount,
    InventorySummary,
    RiskLevelCount,
)
from services.inventory.exposure_signal_service import ExposureSignalService
from services.inventory.inventory_service import AssetInventoryService
from services.risk_engine.confidence import ConfidenceScoringEngine
from services.risk_engine.scoring import RiskScoringEngine


class IntegrationContextService:
    """Builds the read-only AssetContext / InventorySummary payloads
    consumed by other AXERONIX modules (2, 8, 9)."""

    def __init__(
        self,
        inventory_service: AssetInventoryService,
        signal_service: ExposureSignalService,
        risk_engine: RiskScoringEngine,
        confidence_engine: ConfidenceScoringEngine,
    ) -> None:
        self._inventory_service = inventory_service
        self._signal_service = signal_service
        self._risk_engine = risk_engine
        self._confidence_engine = confidence_engine

    def build_context(self, asset: Asset) -> AssetContext:
        """Build the lean context payload for a single, already-fetched
        asset. Split out from get_context() so bulk_context() can reuse
        it without re-fetching each asset it already has in hand."""
        signals = self._signal_service.list_signals_for_asset(asset.id)
        risk_result = self._risk_engine.score_asset(asset, signals)
        confidence_result = self._confidence_engine.score_asset(asset)
        return AssetContext(
            asset_id=asset.id,
            identifier=asset.identifier,
            asset_type=asset.asset_type,
            category=asset.category,
            is_critical=asset.is_critical,
            risk_score=risk_result.total_score,
            risk_level=risk_result.risk_level,
            confidence_score=confidence_result.confidence_score,
        )

    def get_context(self, asset_id: UUID) -> AssetContext | None:
        """Return context for one asset, or None if it doesn't exist —
        the router (not this service) decides whether that's a 404."""
        asset = self._inventory_service.get_asset(asset_id)
        if asset is None:
            return None
        return self.build_context(asset)

    def bulk_context(self, asset_ids: list[UUID]) -> BulkContextResponse:
        """Look up context for many assets in one call. Order of
        `found` is not guaranteed to match the input order — callers
        that need positional alignment should key off `asset_id`."""
        found: list[AssetContext] = []
        not_found: list[UUID] = []
        for asset_id in asset_ids:
            asset = self._inventory_service.get_asset(asset_id)
            if asset is None:
                not_found.append(asset_id)
            else:
                found.append(self.build_context(asset))
        return BulkContextResponse(found=found, not_found=not_found)

    def summarize(self) -> InventorySummary:
        """Aggregate counts across the whole inventory. Every asset is
        scored on demand to build by_risk_level — same cost
        GET /assets?risk_level=... already pays elsewhere in this
        codebase, for the same reason: risk is never persisted."""
        assets = self._inventory_service.list_assets()

        category_counts = Counter(asset.category for asset in assets)
        by_category = [
            CategoryCount(category=category, count=count)
            for category, count in sorted(category_counts.items(), key=lambda kv: kv[0].value)
        ]

        risk_level_counts: Counter[RiskLevel] = Counter()
        for asset in assets:
            signals = self._signal_service.list_signals_for_asset(asset.id)
            result = self._risk_engine.score_asset(asset, signals)
            risk_level_counts[result.risk_level] += 1
        by_risk_level = [
            RiskLevelCount(risk_level=level, count=risk_level_counts.get(level, 0))
            for level in RiskLevel
        ]

        return InventorySummary(
            total_assets=len(assets),
            critical_assets=sum(1 for a in assets if a.is_critical),
            by_category=by_category,
            by_risk_level=by_risk_level,
        )
