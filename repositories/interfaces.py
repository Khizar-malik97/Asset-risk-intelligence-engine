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
from models.enums import AssetCategory


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
    def list_critical(self) -> list[Asset]:
        """Return every asset currently flagged as critical.

        Purpose-built for Milestone 10 (Critical Asset Management), not a
        general filtering capability — the generic multi-filter query layer
        is Milestone 18's job (see docs/scope.md)."""

    @abstractmethod
    def list_by_category(self, category: AssetCategory) -> list[Asset]:
        """Return every asset with this exact category. Same scope note as
        list_critical() above — purpose-built, not general search."""

    @abstractmethod
    def list_hosts(self) -> list[Asset]:
        """Return every asset of type Host.

        Purpose-built for Milestone 17 (Host & User Inventory
        Specialization) — same scope note as list_critical(): not a
        general filter, the generic query layer is Milestone 18's job.
        Return type is list[Asset] (not list[Host]) at the repository
        layer since AssetRepositoryInterface deals in the base type;
        HostInventoryService (Milestone 17) narrows it for callers."""

    @abstractmethod
    def list_users(self) -> list[Asset]:
        """Return every asset of type User. Same scope/typing note as
        list_hosts() above."""

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
