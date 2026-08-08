"""JSON export endpoint (Milestone 21).

A single GET route reusing AssetSearchService's exact filter set (via
ExportService, see services/export/json_export.py) — "export everything
I'd see in a search" is one query string away from GET /assets, never a
separately-maintained filter implementation.
"""

from fastapi import APIRouter, Depends

from api.dependencies import get_export_service
from models.enums import AssetCategory, AssetType, RiskLevel
from models.exposure_signal import ExposureSignalType
from schemas.export import ExportResponse
from services.export.json_export import ExportService

router = APIRouter(prefix="/export", tags=["export"])


@router.get("/assets", response_model=ExportResponse)
def export_assets(
    category: AssetCategory | None = None,
    is_critical: bool | None = None,
    asset_type: AssetType | None = None,
    text: str | None = None,
    exposure_signal_type: ExposureSignalType | None = None,
    risk_level: RiskLevel | None = None,
    service: ExportService = Depends(get_export_service),
) -> ExportResponse:
    """Export the inventory — or a filtered subset — as one JSON
    document. Filters are identical to GET /assets; omit all of them to
    export everything currently in the inventory."""
    return service.export_assets(
        category=category,
        is_critical=is_critical,
        asset_type=asset_type,
        text=text,
        exposure_signal_type=exposure_signal_type,
        risk_level=risk_level,
    )
