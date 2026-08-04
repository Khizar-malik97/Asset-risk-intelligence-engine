"""A fake, in-memory AssetRepositoryInterface implementation, for unit
tests that need to exercise service-layer logic WITHOUT a real database.

Living in tests/ (not repositories/) deliberately — this is test
infrastructure, not a production implementation, and should never be
imported by application code.
"""

from uuid import UUID

from models.asset import Asset
from repositories.exceptions import AssetNotFoundError
from repositories.interfaces import AssetRepositoryInterface


class FakeAssetRepository(AssetRepositoryInterface):
    """Dict-backed fake, sufficient for exercising orchestration logic."""

    def __init__(self) -> None:
        self._store: dict[UUID, Asset] = {}

    def add(self, asset: Asset) -> Asset:
        self._store[asset.id] = asset
        return asset

    def get_by_id(self, asset_id: UUID) -> Asset | None:
        return self._store.get(asset_id)

    def list_all(self) -> list[Asset]:
        return list(self._store.values())

    def update(self, asset: Asset) -> Asset:
        if asset.id not in self._store:
            raise AssetNotFoundError(asset.id)
        self._store[asset.id] = asset
        return asset

    def delete(self, asset_id: UUID) -> None:
        if asset_id not in self._store:
            raise AssetNotFoundError(asset_id)
        del self._store[asset_id]
