"""JSON export service (Milestone 21).

Wraps AssetSearchService rather than reimplementing filtering logic: the
export endpoint supports the exact same filter set GET /assets already
does (category, criticality, type, text, exposure signal, risk level).
Building that filtering twice would reintroduce the exact problem
Milestone 18 solved by centralizing search in one service — "export
everything I'd see in a search" should always be one query-string away
from "see it via GET /assets", never a second, subtly-different
implementation of the same filters.
"""

from datetime import UTC, datetime

from models.enums import AssetCategory, AssetType, RiskLevel
from models.exposure_signal import ExposureSignalType
from schemas.export import AssetExportSchema, ExportResponse
from services.inventory.search import AssetSearchService

EXPORT_SCHEMA_VERSION = 1


class ExportService:
    """Produces a versioned, stable JSON export of the asset inventory."""

    def __init__(self, search_service: AssetSearchService) -> None:
        self._search_service = search_service

    def export_assets(
        self,
        *,
        category: AssetCategory | None = None,
        is_critical: bool | None = None,
        asset_type: AssetType | None = None,
        text: str | None = None,
        exposure_signal_type: ExposureSignalType | None = None,
        risk_level: RiskLevel | None = None,
    ) -> ExportResponse:
        """Export assets matching every given filter (AND semantics, same
        as AssetSearchService.search()). Omitting every filter exports
        the full inventory.

        Raises:
            InvalidRequestError: if risk_level is requested but the
                underlying AssetSearchService has no RiskScoringEngine
                configured — propagated as-is from AssetSearchService.search().
        """
        assets = self._search_service.search(
            category=category,
            is_critical=is_critical,
            asset_type=asset_type,
            text=text,
            exposure_signal_type=exposure_signal_type,
            risk_level=risk_level,
        )
        return ExportResponse(
            schema_version=EXPORT_SCHEMA_VERSION,
            exported_at=datetime.now(UTC),
            asset_count=len(assets),
            assets=[AssetExportSchema.model_validate(asset) for asset in assets],
        )
