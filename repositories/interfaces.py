"""Abstract repository interface for Asset persistence.

The Service Layer (Milestone 8 onward) depends on THIS interface, not on
SQLAlchemyAssetRepository directly. This is the Dependency Inversion
Principle in practice: swap the concrete implementation (e.g. for a test
double, or a future non-SQL backend) without touching a single line of
business logic.
"""

from abc import ABC, abstractmethod
from uuid import UUID

from models.asset import Asset


class AssetRepositoryInterface(ABC):
    """Contract for any storage backend that persists Asset (and subtypes)."""

    @abstractmethod
    def add(self, asset: Asset) -> Asset:
        """Persist a new asset. Returns the persisted asset (with any
        storage-assigned defaults applied, though id is already client-side)."""

    @abstractmethod
    def get_by_id(self, asset_id: UUID) -> Asset | None:
        """Return the asset with this id, or None if it doesn't exist."""

    @abstractmethod
    def get_by_identifier(self, identifier: str) -> Asset | None:
        """Return the asset with this exact identifier, or None if none
        exists. Used by the service layer for duplicate detection on
        manual registration (Milestone 9) — not a general search/filter
        capability (that's Milestone 18)."""

    @abstractmethod
    def list_all(self) -> list[Asset]:
        """Return every asset in the inventory, regardless of type."""

    @abstractmethod
    def update(self, asset: Asset) -> Asset:
        """Persist changes to an existing asset.

        Raises:
            AssetNotFoundError: if no asset with this id exists.
        """

    @abstractmethod
    def delete(self, asset_id: UUID) -> None:
        """Remove an asset from the inventory.

        Raises:
            AssetNotFoundError: if no asset with this id exists.
        """
