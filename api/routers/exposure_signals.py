"""Exposure signal endpoints not scoped under a specific asset.

Attaching and listing signals lives in api/routers/assets.py, since both
are naturally asset-scoped (POST/GET /assets/{asset_id}/exposure-signals).
Removal is by the signal's own id, not the asset's, so it gets its own
top-level route here instead.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from api.dependencies import get_exposure_signal_service
from services.inventory.exposure_signal_service import ExposureSignalService

router = APIRouter(prefix="/exposure-signals", tags=["exposure-signals"])


@router.delete("/{signal_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_exposure_signal(
    signal_id: UUID,
    service: ExposureSignalService = Depends(get_exposure_signal_service),
) -> None:
    """Remove an exposure signal by its own id.

    ExposureSignalRepository.remove() raises a plain ValueError for "not
    found" (see repositories/exposure_signal_repository.py) rather than a
    dedicated exception type — caught locally here rather than via a
    global handler, since a bare ValueError is too generic a signal to
    safely map to 404 everywhere in the app (see api/main.py's exception
    handler docstring for why DuplicateAssetError/AssetNotFoundError get
    global handlers and this doesn't).
    """
    try:
        service.remove_signal(signal_id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
