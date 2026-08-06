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
from models.enums import AssetCategory, AssetType


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

    def search(
        self,
        *,
        category: AssetCategory | None = None,
        is_critical: bool | None = None,
        asset_type: AssetType | None = None,
        text: str | None = None,
    ) -> list[Asset]:
        """Return assets matching all of the given filters (AND semantics).
        Every parameter left as None is ignored (not filtered on).

        This is a CONCRETE method with a default, naive implementation —
        deliberately not abstract, so existing repository implementations
        (e.g. test doubles) keep working without modification. It filters
        list_all() in plain Python, which is correct but not efficient.

        A concrete repository backed by a real database SHOULD override
        this with an equivalent, SQL-pushed-down implementation for
        performance — see SQLAlchemyAssetRepository.search() (Milestone 18).

        Args:
            category: exact category match.
            is_critical: exact criticality flag match.
            asset_type: exact asset type match (generic/host/user).
            text: case-insensitive substring match against `identifier`.
        """
        results = self.list_all()

        if category is not None:
            results = [a for a in results if a.category == category]
        if is_critical is not None:
            results = [a for a in results if a.is_critical == is_critical]
        if asset_type is not None:
            results = [a for a in results if a.asset_type == asset_type]
        if text:
            lowered = text.lower()
            results = [a for a in results if lowered in a.identifier.lower()]

        return results
