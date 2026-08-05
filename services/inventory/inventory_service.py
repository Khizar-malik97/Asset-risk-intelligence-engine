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
from models.enums import AssetCategory
from repositories.exceptions import AssetNotFoundError
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

    def flag_as_critical(self, asset_id: UUID) -> Asset:
        """Mark an asset as business-critical.

        This is a deliberate human decision, not a computed property — it
        does not get set or unset by anything the Risk Engine calculates
        (Milestone 12 onward). It instead feeds IN as one of the Risk
        Engine's input factors, the same direction exposure signals will
        (Milestone 11).

        Raises:
            AssetNotFoundError: if no asset with this id exists.
        """
        asset = self._get_asset_or_raise(asset_id)
        asset.is_critical = True
        updated = self._repository.update(asset)
        logger.info(
            "Asset flagged as critical",
            extra={"asset_id": str(updated.id), "identifier": updated.identifier},
        )
        return updated

    def unflag_as_critical(self, asset_id: UUID) -> Asset:
        """Remove the business-critical flag from an asset.

        Raises:
            AssetNotFoundError: if no asset with this id exists.
        """
        asset = self._get_asset_or_raise(asset_id)
        asset.is_critical = False
        updated = self._repository.update(asset)
        logger.info(
            "Asset unflagged as critical",
            extra={"asset_id": str(updated.id), "identifier": updated.identifier},
        )
        return updated

    def assign_category(self, asset_id: UUID, category: AssetCategory) -> Asset:
        """Set an asset's business classification (server, workstation, etc).

        Raises:
            AssetNotFoundError: if no asset with this id exists.
        """
        asset = self._get_asset_or_raise(asset_id)
        asset.category = category
        updated = self._repository.update(asset)
        logger.info(
            "Asset category assigned",
            extra={
                "asset_id": str(updated.id),
                "identifier": updated.identifier,
                "category": str(category),
            },
        )
        return updated

    def list_critical_assets(self) -> list[Asset]:
        """Return every asset currently flagged as critical."""
        return self._repository.list_critical()

    def list_assets_by_category(self, category: AssetCategory) -> list[Asset]:
        """Return every asset with this exact category."""
        return self._repository.list_by_category(category)

    def _get_asset_or_raise(self, asset_id: UUID) -> Asset:
        """Shared lookup for the flag/category operations above: they all
        need to fetch-then-modify-then-update, and all need the same clear
        error when the asset doesn't exist."""
        asset = self._repository.get_by_id(asset_id)
        if asset is None:
            raise AssetNotFoundError(asset_id)
        return asset
