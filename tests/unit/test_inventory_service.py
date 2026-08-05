"""Unit tests for AssetInventoryService.

Uses FakeAssetRepository (in-memory), not a real database — these tests
verify orchestration logic only: does the service call the repository
correctly and propagate results/errors as expected?
"""

import uuid

import pytest

from models.asset import Asset
from models.enums import AssetCategory
from models.host import Host
from repositories.exceptions import AssetNotFoundError
from services.exceptions import DuplicateAssetError
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

    def test_duplicate_identifier_is_rejected(self, service):
        service.register_asset(Asset(identifier="dup-host"))

        with pytest.raises(DuplicateAssetError):
            service.register_asset(Asset(identifier="dup-host"))

    def test_duplicate_rejection_leaves_original_untouched(self, service):
        original = service.register_asset(Host(identifier="dup-host-2", ip_address="10.0.0.1"))

        with pytest.raises(DuplicateAssetError):
            service.register_asset(Host(identifier="dup-host-2", ip_address="10.0.0.2"))

        unchanged = service.get_asset(original.id)
        assert unchanged.ip_address == "10.0.0.1"

    def test_different_identifiers_do_not_collide(self, service):
        service.register_asset(Asset(identifier="host-a"))

        # Should not raise
        result = service.register_asset(Asset(identifier="host-b"))
        assert result.identifier == "host-b"


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


class TestCriticalFlagging:
    def test_flag_as_critical_sets_the_flag(self, service):
        asset = service.register_asset(Asset(identifier="crown-jewel"))
        assert asset.is_critical is False

        updated = service.flag_as_critical(asset.id)

        assert updated.is_critical is True

    def test_flag_as_critical_persists(self, service):
        asset = service.register_asset(Asset(identifier="crown-jewel-2"))
        service.flag_as_critical(asset.id)

        refetched = service.get_asset(asset.id)

        assert refetched.is_critical is True

    def test_flag_nonexistent_raises(self, service):
        with pytest.raises(AssetNotFoundError):
            service.flag_as_critical(uuid.uuid4())

    def test_unflag_as_critical_clears_the_flag(self, service):
        asset = service.register_asset(Asset(identifier="was-critical"))
        service.flag_as_critical(asset.id)

        updated = service.unflag_as_critical(asset.id)

        assert updated.is_critical is False

    def test_unflag_nonexistent_raises(self, service):
        with pytest.raises(AssetNotFoundError):
            service.unflag_as_critical(uuid.uuid4())

    def test_list_critical_assets_returns_only_flagged(self, service):
        critical = service.register_asset(Asset(identifier="critical-one"))
        service.register_asset(Asset(identifier="not-critical"))
        service.flag_as_critical(critical.id)

        result = service.list_critical_assets()

        assert len(result) == 1
        assert result[0].id == critical.id

    def test_list_critical_assets_empty_when_none_flagged(self, service):
        service.register_asset(Asset(identifier="not-critical"))

        assert service.list_critical_assets() == []


class TestCategoryAssignment:
    def test_assign_category_sets_it(self, service):
        asset = service.register_asset(Asset(identifier="db-01"))
        assert asset.category == AssetCategory.UNCATEGORIZED

        updated = service.assign_category(asset.id, AssetCategory.DATABASE_SERVER)

        assert updated.category == AssetCategory.DATABASE_SERVER

    def test_assign_category_persists(self, service):
        asset = service.register_asset(Asset(identifier="db-02"))
        service.assign_category(asset.id, AssetCategory.DATABASE_SERVER)

        refetched = service.get_asset(asset.id)

        assert refetched.category == AssetCategory.DATABASE_SERVER

    def test_assign_category_nonexistent_raises(self, service):
        with pytest.raises(AssetNotFoundError):
            service.assign_category(uuid.uuid4(), AssetCategory.SERVER)

    def test_list_assets_by_category_returns_matching_only(self, service):
        server = service.register_asset(Asset(identifier="srv-01"))
        service.assign_category(server.id, AssetCategory.SERVER)
        service.register_asset(Asset(identifier="workstation-01"))

        result = service.list_assets_by_category(AssetCategory.SERVER)

        assert len(result) == 1
        assert result[0].id == server.id

    def test_list_assets_by_category_empty_when_no_match(self, service):
        service.register_asset(Asset(identifier="uncategorized-1"))

        assert service.list_assets_by_category(AssetCategory.NETWORK_DEVICE) == []
