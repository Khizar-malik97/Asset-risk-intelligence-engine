"""Asset Inventory Service.

The business-logic orchestration layer for asset CRUD. Depends on
AssetRepositoryInterface, not any concrete repository implementation —
this is what makes it fully unit-testable without a real database, and
what will let the API layer (Milestone 19) call use-cases instead of
knowing anything about persistence.
"""

from uuid import UUID

from logging_.logger import get_logger
from models.asset import Asset
from repositories.interfaces import AssetRepositoryInterface
from services.exceptions import DuplicateAssetError

logger = get_logger(__name__)


class AssetInventoryService:
    """Use-case layer for registering, retrieving, updating, deleting, and
    listing assets."""

    def __init__(self, repository: AssetRepositoryInterface) -> None:
        self._repository = repository

    def register_asset(self, asset: Asset) -> Asset:
        """Register a new asset in the inventory.

        Rejects exact-identifier duplicates (Milestone 9) — see
        services/exceptions.py::DuplicateAssetError for how this differs
        from Discovery Reconciliation (Milestone 16).

        Raises:
            DuplicateAssetError: if an asset with this identifier is
                already registered.
        """
        existing = self._repository.get_by_identifier(asset.identifier)
        if existing is not None:
            logger.info(
                "Asset registration rejected: duplicate identifier",
                extra={"identifier": asset.identifier, "existing_asset_id": str(existing.id)},
            )
            raise DuplicateAssetError(asset.identifier)

        saved = self._repository.add(asset)
        logger.info(
            "Asset registered",
            extra={"asset_id": str(saved.id), "identifier": saved.identifier},
        )
        return saved

    def get_asset(self, asset_id: UUID) -> Asset | None:
        """Retrieve a single asset by id, or None if it doesn't exist."""
        return self._repository.get_by_id(asset_id)

    def list_assets(self) -> list[Asset]:
        """Return every asset in the inventory."""
        return self._repository.list_all()

    def update_asset(self, asset: Asset) -> Asset:
        """Persist changes to an existing asset.

        Raises:
            AssetNotFoundError: if no asset with this id exists (propagated
                unchanged from the repository layer).
        """
        updated = self._repository.update(asset)
        logger.info(
            "Asset updated",
            extra={"asset_id": str(updated.id), "identifier": updated.identifier},
        )
        return updated

    def delete_asset(self, asset_id: UUID) -> None:
        """Remove an asset from the inventory.

        Raises:
            AssetNotFoundError: if no asset with this id exists.
        """
        self._repository.delete(asset_id)
        logger.info("Asset deleted", extra={"asset_id": str(asset_id)})
