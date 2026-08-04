"""Unit tests for the core domain models: Asset, Host, User."""

from datetime import UTC, datetime, timedelta

import pytest

from models.asset import Asset
from models.enums import AssetCategory, AssetType, DiscoverySource
from models.host import Host
from models.user import User


class TestAsset:
    def test_construct_with_defaults(self):
        asset = Asset(identifier="generic-001")

        assert asset.identifier == "generic-001"
        assert asset.asset_type == AssetType.GENERIC
        assert asset.category == AssetCategory.UNCATEGORIZED
        assert asset.is_critical is False
        assert asset.discovery_source == DiscoverySource.MANUAL
        assert asset.id is not None

    def test_empty_identifier_is_rejected(self):
        with pytest.raises(ValueError):
            Asset(identifier="")

    def test_whitespace_only_identifier_is_rejected(self):
        with pytest.raises(ValueError):
            Asset(identifier="   ")

    def test_two_assets_get_different_ids(self):
        a1 = Asset(identifier="host-a")
        a2 = Asset(identifier="host-b")

        assert a1.id != a2.id

    def test_is_stale_true_when_last_seen_old(self):
        asset = Asset(identifier="stale-host")
        asset.last_seen = datetime.now(UTC) - timedelta(days=45)

        assert asset.is_stale(staleness_threshold_days=30) is True

    def test_is_stale_false_when_recently_seen(self):
        asset = Asset(identifier="fresh-host")
        asset.last_seen = datetime.now(UTC) - timedelta(days=1)

        assert asset.is_stale(staleness_threshold_days=30) is False

    def test_is_stale_boundary_exactly_at_threshold(self):
        asset = Asset(identifier="boundary-host")
        asset.last_seen = datetime.now(UTC) - timedelta(days=30)

        assert asset.is_stale(staleness_threshold_days=30) is True

    def test_mark_seen_updates_last_seen(self):
        asset = Asset(identifier="host-x")
        asset.last_seen = datetime.now(UTC) - timedelta(days=10)

        asset.mark_seen()

        assert asset.is_stale(staleness_threshold_days=1) is False

    def test_age_in_days(self):
        asset = Asset(identifier="host-y")
        asset.first_seen = datetime.now(UTC) - timedelta(days=5)

        assert asset.age_in_days() == 5


class TestHost:
    def test_construct_sets_host_type_automatically(self):
        host = Host(identifier="web-01")

        assert host.asset_type == AssetType.HOST

    def test_host_specific_fields_default_correctly(self):
        host = Host(identifier="web-02")

        assert host.ip_address is None
        assert host.operating_system is None
        assert host.is_internet_facing is False

    def test_host_specific_fields_can_be_set(self):
        host = Host(
            identifier="web-03",
            ip_address="10.2.4.9",
            operating_system="Ubuntu 24.04",
            is_internet_facing=True,
        )

        assert host.ip_address == "10.2.4.9"
        assert host.operating_system == "Ubuntu 24.04"
        assert host.is_internet_facing is True

    def test_host_still_validates_empty_identifier(self):
        with pytest.raises(ValueError):
            Host(identifier="")

    def test_host_inherits_asset_behavior(self):
        host = Host(identifier="web-04")
        host.last_seen = datetime.now(UTC) - timedelta(days=60)

        assert host.is_stale() is True


class TestUser:
    def test_construct_sets_user_type_automatically(self):
        user = User(identifier="jdoe")

        assert user.asset_type == AssetType.USER

    def test_user_specific_fields_default_correctly(self):
        user = User(identifier="jdoe")

        assert user.is_privileged is False
        assert user.department is None

    def test_user_specific_fields_can_be_set(self):
        user = User(identifier="admin_jdoe", is_privileged=True, department="IT")

        assert user.is_privileged is True
        assert user.department == "IT"

    def test_user_still_validates_empty_identifier(self):
        with pytest.raises(ValueError):
            User(identifier="")
