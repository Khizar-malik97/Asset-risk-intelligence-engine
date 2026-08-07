"""Exposure signal endpoints not scoped under a specific asset.

Attaching and listing signals lives in api/routers/assets.py, since both
are naturally asset-scoped (POST/GET /assets/{asset_id}/exposure-signals).
Removal is by the signal's own id, not the asset's, so it gets its own
top-level route here instead.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, status

from api.dependencies import get_exposure_signal_service
from services.inventory.exposure_signal_service import ExposureSignalService

router = APIRouter(prefix="/exposure-signals", tags=["exposure-signals"])


@router.delete("/{signal_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_exposure_signal(
    signal_id: UUID,
    service: ExposureSignalService = Depends(get_exposure_signal_service),
) -> None:
    """Remove an exposure signal by its own id.

    ExposureSignalRepository.remove() now raises the typed
    ExposureSignalNotFoundError (Milestone 20) instead of a bare
    ValueError — it's an AppError subclass, so api/main.py's single
    global handler produces the standard error envelope automatically.
    No local try/except needed here anymore.
    """
    service.remove_signal(signal_id)
