"""Unit tests for AssetInventoryService.

Uses FakeAssetRepository (in-memory), not a real database — these tests
verify orchestration logic only: does the service call the repository
correctly and propagate results/errors as expected?
"""

import uuid

import pytest

from models.asset import Asset
from models.host import Host
from repositories.exceptions import AssetNotFoundError
from services.inventory.inventory_service import AssetInventoryService
from tests.fakes.fake_asset_repository import FakeAssetRepository


@pytest.fixture()
def service():
    return AssetInventoryService(repository=FakeAssetRepository())


class TestRegisterAsset:
    def test_register_returns_the_saved_asset(self, service):
        asset = Asset(identifier="new-asset")

        result = service.register_asset(asset)

        assert result.id == asset.id
        assert result.identifier == "new-asset"

    def test_register_makes_asset_retrievable(self, service):
        asset = Asset(identifier="new-asset")
        service.register_asset(asset)

        fetched = service.get_asset(asset.id)

        assert fetched is not None
        assert fetched.identifier == "new-asset"


class TestGetAsset:
    def test_get_nonexistent_returns_none(self, service):
        assert service.get_asset(uuid.uuid4()) is None


class TestListAssets:
    def test_list_empty_inventory(self, service):
        assert service.list_assets() == []

    def test_list_returns_all_registered_assets(self, service):
        service.register_asset(Asset(identifier="a1"))
        service.register_asset(Host(identifier="h1"))

        result = service.list_assets()

        assert len(result) == 2


class TestUpdateAsset:
    def test_update_existing_asset(self, service):
        asset = service.register_asset(Asset(identifier="original"))
        asset.identifier = "renamed"

        updated = service.update_asset(asset)

        assert updated.identifier == "renamed"

    def test_update_nonexistent_raises(self, service):
        phantom = Asset(identifier="ghost")

        with pytest.raises(AssetNotFoundError):
            service.update_asset(phantom)


class TestDeleteAsset:
    def test_delete_existing_asset(self, service):
        asset = service.register_asset(Asset(identifier="to-delete"))

        service.delete_asset(asset.id)

        assert service.get_asset(asset.id) is None

    def test_delete_nonexistent_raises(self, service):
        with pytest.raises(AssetNotFoundError):
            service.delete_asset(uuid.uuid4())
