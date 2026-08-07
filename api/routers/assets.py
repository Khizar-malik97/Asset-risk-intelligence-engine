"""Asset-related API endpoints.

Every endpoint here is a thin translation layer: parse/validate the
request (Pydantic, mostly handled by FastAPI automatically), call exactly
one service method, translate the result to a response schema. No business
logic lives in this file — that's the whole point of everything built in
Milestones 5-18.

Error handling is intentionally minimal here: DuplicateAssetError and
AssetNotFoundError are caught globally in api/main.py's exception
handlers (409 / 404 respectively) since they mean the same thing no
matter which endpoint raises them. Full error-response standardization
(consistent error body shape, documented error codes) is Milestone 20's
job — this milestone only needs correct status codes.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, status

from api.dependencies import (
    get_confidence_scoring_engine,
    get_exposure_signal_service,
    get_host_inventory_service,
    get_inventory_service,
    get_risk_scoring_engine,
    get_search_service,
    get_user_inventory_service,
)
from models.enums import AssetCategory, AssetType, RiskLevel
from models.exposure_signal import ExposureSignalType
from repositories.exceptions import AssetNotFoundError
from schemas.asset import (
    AssetRegistrationRequest,
    CategoryAssignmentRequest,
    HostRegistrationRequest,
    UserRegistrationRequest,
)
from schemas.exposure_signal import ExposureSignalAttachRequest
from schemas.responses import (
    AssetResponse,
    ConfidenceScoreResponse,
    ExposureSignalResponse,
    RiskScoreResponse,
)
from services.inventory.exposure_signal_service import ExposureSignalService
from services.inventory.host_inventory_service import HostInventoryService
from services.inventory.inventory_service import AssetInventoryService
from services.inventory.search import AssetSearchService
from services.inventory.user_inventory_service import UserInventoryService
from services.risk_engine.confidence import ConfidenceScoringEngine
from services.risk_engine.scoring import RiskScoringEngine

router = APIRouter(prefix="/assets", tags=["assets"])


# --- Registration -----------------------------------------------------------


@router.post("", response_model=AssetResponse, status_code=status.HTTP_201_CREATED)
def register_asset(
    request: AssetRegistrationRequest,
    service: AssetInventoryService = Depends(get_inventory_service),
) -> AssetResponse:
    """Register a generic asset (not a host or user account)."""
    asset = service.register_asset(request.to_domain())
    return AssetResponse.model_validate(asset)


@router.post("/hosts", response_model=AssetResponse, status_code=status.HTTP_201_CREATED)
def register_host(
    request: HostRegistrationRequest,
    service: HostInventoryService = Depends(get_host_inventory_service),
) -> AssetResponse:
    """Register a host asset."""
    host = service.register_host(request.to_domain())
    return AssetResponse.model_validate(host)


@router.post("/users", response_model=AssetResponse, status_code=status.HTTP_201_CREATED)
def register_user(
    request: UserRegistrationRequest,
    service: UserInventoryService = Depends(get_user_inventory_service),
) -> AssetResponse:
    """Register a user-account asset."""
    user = service.register_user(request.to_domain())
    return AssetResponse.model_validate(user)


# --- Retrieval & search -------------------------------------------------------
# NOTE: these two routes must be declared before the /{asset_id} routes
# below — FastAPI matches path routes in declaration order, and "critical"
# or "hosts" would otherwise be swallowed by /{asset_id} as a literal id.


@router.get("/critical", response_model=list[AssetResponse])
def list_critical_assets(
    service: AssetInventoryService = Depends(get_inventory_service),
) -> list[AssetResponse]:
    """List every asset currently flagged as business-critical."""
    return [AssetResponse.model_validate(a) for a in service.list_critical_assets()]


@router.get("/hosts", response_model=list[AssetResponse])
def list_hosts(
    service: HostInventoryService = Depends(get_host_inventory_service),
) -> list[AssetResponse]:
    """List every host asset."""
    return [AssetResponse.model_validate(h) for h in service.list_hosts()]


@router.get("/users", response_model=list[AssetResponse])
def list_users(
    service: UserInventoryService = Depends(get_user_inventory_service),
) -> list[AssetResponse]:
    """List every user-account asset."""
    return [AssetResponse.model_validate(u) for u in service.list_users()]


@router.get("", response_model=list[AssetResponse])
def search_assets(
    category: AssetCategory | None = None,
    is_critical: bool | None = None,
    asset_type: AssetType | None = None,
    text: str | None = None,
    exposure_signal_type: ExposureSignalType | None = None,
    risk_level: RiskLevel | None = None,
    service: AssetSearchService = Depends(get_search_service),
) -> list[AssetResponse]:
    """List/search assets. With no query parameters, returns everything —
    every filter is optional and combines with AND semantics (Milestone 18)."""
    results = service.search(
        category=category,
        is_critical=is_critical,
        asset_type=asset_type,
        text=text,
        exposure_signal_type=exposure_signal_type,
        risk_level=risk_level,
    )
    return [AssetResponse.model_validate(a) for a in results]


@router.get("/{asset_id}", response_model=AssetResponse)
def get_asset(
    asset_id: UUID,
    service: AssetInventoryService = Depends(get_inventory_service),
) -> AssetResponse:
    """Retrieve a single asset by id."""
    asset = service.get_asset(asset_id)
    if asset is None:
        raise AssetNotFoundError(asset_id)
    return AssetResponse.model_validate(asset)


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_asset(
    asset_id: UUID,
    service: AssetInventoryService = Depends(get_inventory_service),
) -> None:
    """Remove an asset from the inventory."""
    service.delete_asset(asset_id)


# --- Criticality & category ---------------------------------------------------


@router.put("/{asset_id}/critical", response_model=AssetResponse)
def flag_as_critical(
    asset_id: UUID,
    service: AssetInventoryService = Depends(get_inventory_service),
) -> AssetResponse:
    """Flag an asset as business-critical. Idempotent — flagging an
    already-critical asset just returns it unchanged."""
    return AssetResponse.model_validate(service.flag_as_critical(asset_id))


@router.delete("/{asset_id}/critical", response_model=AssetResponse)
def unflag_as_critical(
    asset_id: UUID,
    service: AssetInventoryService = Depends(get_inventory_service),
) -> AssetResponse:
    """Remove the business-critical flag from an asset."""
    return AssetResponse.model_validate(service.unflag_as_critical(asset_id))


@router.patch("/{asset_id}/category", response_model=AssetResponse)
def assign_category(
    asset_id: UUID,
    request: CategoryAssignmentRequest,
    service: AssetInventoryService = Depends(get_inventory_service),
) -> AssetResponse:
    """Set an asset's business classification (server, workstation, etc)."""
    return AssetResponse.model_validate(service.assign_category(asset_id, request.category))


# --- Exposure signals ----------------------------------------------------------


@router.post(
    "/{asset_id}/exposure-signals",
    response_model=ExposureSignalResponse,
    status_code=status.HTTP_201_CREATED,
)
def attach_exposure_signal(
    asset_id: UUID,
    request: ExposureSignalAttachRequest,
    inventory_service: AssetInventoryService = Depends(get_inventory_service),
    signal_service: ExposureSignalService = Depends(get_exposure_signal_service),
) -> ExposureSignalResponse:
    """Attach an exposure signal to an asset.

    Confirms the asset exists first — ExposureSignalService itself doesn't
    check this (see its docstring: it deliberately avoids depending on
    AssetRepository), so that check belongs here, at the layer that already
    depends on both services.
    """
    if inventory_service.get_asset(asset_id) is None:
        raise AssetNotFoundError(asset_id)

    signal = signal_service.attach_signal(
        asset_id=asset_id,
        signal_type=request.signal_type,
        severity=request.severity,
        description=request.description,
    )
    return ExposureSignalResponse.model_validate(signal)


@router.get("/{asset_id}/exposure-signals", response_model=list[ExposureSignalResponse])
def list_exposure_signals(
    asset_id: UUID,
    service: ExposureSignalService = Depends(get_exposure_signal_service),
) -> list[ExposureSignalResponse]:
    """List every exposure signal attached to an asset, most recent first."""
    signals = service.list_signals_for_asset(asset_id)
    return [ExposureSignalResponse.model_validate(s) for s in signals]


# --- Risk & confidence -----------------------------------------------------------


@router.get("/{asset_id}/risk", response_model=RiskScoreResponse)
def get_asset_risk(
    asset_id: UUID,
    inventory_service: AssetInventoryService = Depends(get_inventory_service),
    signal_service: ExposureSignalService = Depends(get_exposure_signal_service),
    risk_engine: RiskScoringEngine = Depends(get_risk_scoring_engine),
) -> RiskScoreResponse:
    """Return an asset's current risk score, level, and full per-factor
    explanation. Computed on demand — nothing about risk scoring is
    persisted (see docs/architecture.md's Risk Scoring Strategy: scores
    are always recomputed from current data, never cached, so they can
    never silently go stale)."""
    asset = inventory_service.get_asset(asset_id)
    if asset is None:
        raise AssetNotFoundError(asset_id)

    signals = signal_service.list_signals_for_asset(asset_id)
    result = risk_engine.score_asset(asset, signals)
    return RiskScoreResponse.model_validate(result)


@router.get("/{asset_id}/confidence", response_model=ConfidenceScoreResponse)
def get_asset_confidence(
    asset_id: UUID,
    inventory_service: AssetInventoryService = Depends(get_inventory_service),
    confidence_engine: ConfidenceScoringEngine = Depends(get_confidence_scoring_engine),
) -> ConfidenceScoreResponse:
    """Return how much to trust an asset's current data — independent of
    (never blended with) its risk score. See
    services/risk_engine/confidence.py for why these stay separate."""
    asset = inventory_service.get_asset(asset_id)
    if asset is None:
        raise AssetNotFoundError(asset_id)

    result = confidence_engine.score_asset(asset)
    return ConfidenceScoreResponse.model_validate(result)
