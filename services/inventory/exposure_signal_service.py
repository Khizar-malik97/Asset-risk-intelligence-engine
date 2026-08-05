"""Service layer for attaching/removing exposure signals on assets.

Kept as its own small service (rather than folded into InventoryService)
since it operates on a distinct table with its own repository. Wire it
alongside InventoryService wherever assets are managed.
"""

from uuid import UUID

from logging_.logger import get_logger
from models.exposure_signal import ExposureSeverity, ExposureSignal, ExposureSignalType
from repositories.exposure_signal_repository import ExposureSignalRepositoryInterface

logger = get_logger(__name__)


class ExposureSignalService:
    """Attach, list, and remove exposure signals for assets."""

    def __init__(self, repository: ExposureSignalRepositoryInterface) -> None:
        self._repository = repository

    def attach_signal(
        self,
        asset_id: UUID,
        signal_type: ExposureSignalType,
        severity: ExposureSeverity,
        description: str,
    ) -> ExposureSignal:
        """Attach a new exposure signal to an asset.

        Note: this does not verify the asset exists — that check belongs to
        whichever layer calls this alongside InventoryService, to avoid this
        service depending on AssetRepository as well.
        """
        signal = ExposureSignal(
            asset_id=asset_id,
            signal_type=signal_type,
            severity=severity,
            description=description,
        )
        saved = self._repository.add(signal)
        logger.info(
            "Exposure signal attached",
            extra={"asset_id": str(asset_id), "signal_type": signal_type.value},
        )
        return saved

    def list_signals_for_asset(self, asset_id: UUID) -> list[ExposureSignal]:
        """Return all exposure signals attached to an asset, most recent first."""
        return self._repository.list_for_asset(asset_id)

    def remove_signal(self, signal_id: UUID) -> None:
        """Remove an exposure signal by its own ID."""
        self._repository.remove(signal_id)
        logger.info("Exposure signal removed", extra={"signal_id": str(signal_id)})
