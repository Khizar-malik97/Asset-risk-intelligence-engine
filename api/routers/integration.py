"""Read-only integration API for other AXERONIX modules (Milestone 26).

Base path /integration. Every route here is read-only by design — this
is a consumption contract for Modules 2 (Event Correlation Engine), 8
(Detection Quality Engine), and 9 (Executive Dashboard), not a general
CRUD surface. Registration, mutation, and deletion all stay under
/assets — see api/routers/assets.py.
"""

from uuid import UUID

from fastapi import APIRouter, Depends

from api.dependencies import (
    get_confidence_scoring_engine,
    get_exposure_signal_service,
    get_inventory_service,
    get_risk_scoring_engine,
)
from repositories.exceptions import AssetNotFoundError
from schemas.integration import (
    AssetContext,
    BulkContextRequest,
    BulkContextResponse,
    InventorySummary,
)
from services.integration.context_service import IntegrationContextService
from services.inventory.exposure_signal_service import ExposureSignalService
from services.inventory.inventory_service import AssetInventoryService
from services.risk_engine.confidence import ConfidenceScoringEngine
from services.risk_engine.scoring import RiskScoringEngine

router = APIRouter(prefix="/integration", tags=["integration"])


def _build_service(
    inventory_service: AssetInventoryService,
    signal_service: ExposureSignalService,
    risk_engine: RiskScoringEngine,
    confidence_engine: ConfidenceScoringEngine,
) -> IntegrationContextService:
    return IntegrationContextService(
        inventory_service, signal_service, risk_engine, confidence_engine
    )


@router.get("/assets/{asset_id}/context", response_model=AssetContext)
def get_asset_context(
    asset_id: UUID,
    inventory_service: AssetInventoryService = Depends(get_inventory_service),
    signal_service: ExposureSignalService = Depends(get_exposure_signal_service),
    risk_engine: RiskScoringEngine = Depends(get_risk_scoring_engine),
    confidence_engine: ConfidenceScoringEngine = Depends(get_confidence_scoring_engine),
) -> AssetContext:
    """Single-asset lean context: identity, criticality, risk, confidence.

    The read Module 2 makes when enriching one alert at a time. For a
    batch of alerts, prefer POST /integration/assets/context instead of
    calling this in a loop.
    """
    service = _build_service(inventory_service, signal_service, risk_engine, confidence_engine)
    context = service.get_context(asset_id)
    if context is None:
        raise AssetNotFoundError(asset_id)
    return context


@router.post("/assets/context", response_model=BulkContextResponse)
def bulk_asset_context(
    request: BulkContextRequest,
    inventory_service: AssetInventoryService = Depends(get_inventory_service),
    signal_service: ExposureSignalService = Depends(get_exposure_signal_service),
    risk_engine: RiskScoringEngine = Depends(get_risk_scoring_engine),
    confidence_engine: ConfidenceScoringEngine = Depends(get_confidence_scoring_engine),
) -> BulkContextResponse:
    """Batch lookup — up to 500 asset ids per call. The intended shape
    for Module 2 correlating a burst of events: one request instead of
    one GET per asset. Ids that don't exist come back in `not_found`,
    never silently dropped."""
    service = _build_service(inventory_service, signal_service, risk_engine, confidence_engine)
    return service.bulk_context(request.asset_ids)


@router.get("/summary", response_model=InventorySummary)
def get_inventory_summary(
    inventory_service: AssetInventoryService = Depends(get_inventory_service),
    signal_service: ExposureSignalService = Depends(get_exposure_signal_service),
    risk_engine: RiskScoringEngine = Depends(get_risk_scoring_engine),
    confidence_engine: ConfidenceScoringEngine = Depends(get_confidence_scoring_engine),
) -> InventorySummary:
    """Aggregate inventory counts — total, critical, by category, by
    risk level. The shape Module 9's Executive Dashboard actually wants:
    rolled-up numbers, not every asset record."""
    service = _build_service(inventory_service, signal_service, risk_engine, confidence_engine)
    return service.summarize()
