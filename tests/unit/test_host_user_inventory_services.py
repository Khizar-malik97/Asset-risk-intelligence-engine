"""Unit tests for HostInventoryService and UserInventoryService."""

import uuid

import pytest

from models.asset import Asset
from models.host import Host
from models.user import User
from services.exceptions import DuplicateAssetError
from services.inventory.host_inventory_service import HostInventoryService
from services.inventory.user_inventory_service import UserInventoryService
from tests.fakes.fake_asset_repository import FakeAssetRepository


@pytest.fixture()
def host_service() -> HostInventoryService:
    return HostInventoryService(repository=FakeAssetRepository())


@pytest.fixture()
def user_service() -> UserInventoryService:
    return UserInventoryService(repository=FakeAssetRepository())


class TestHostInventoryService:
    def test_register_host_returns_saved_host(self, host_service: HostInventoryService) -> None:
        host = Host(identifier="web-01", ip_address="10.0.0.1")

        saved = host_service.register_host(host)

        assert isinstance(saved, Host)
        assert saved.ip_address == "10.0.0.1"

    def test_register_duplicate_identifier_rejected(
        self, host_service: HostInventoryService
    ) -> None:
        host_service.register_host(Host(identifier="dup-host"))

        with pytest.raises(DuplicateAssetError):
            host_service.register_host(Host(identifier="dup-host"))

    def test_get_host_returns_none_for_missing_id(self, host_service: HostInventoryService) -> None:
        assert host_service.get_host(uuid.uuid4()) is None

    def test_get_host_returns_none_for_non_host_asset(self) -> None:
        """A generic Asset (or User) sharing an id space with hosts should
        never be returned by get_host — this service only surfaces Hosts."""
        repository = FakeAssetRepository()
        generic = repository.add(Asset(identifier="not-a-host"))
        host_service = HostInventoryService(repository=repository)

        assert host_service.get_host(generic.id) is None

    def test_get_host_returns_the_host(self, host_service: HostInventoryService) -> None:
        saved = host_service.register_host(Host(identifier="web-02"))

        fetched = host_service.get_host(saved.id)

        assert fetched is not None
        assert fetched.id == saved.id

    def test_list_hosts_returns_only_hosts(self) -> None:
        repository = FakeAssetRepository()
        repository.add(Host(identifier="h1"))
        repository.add(Host(identifier="h2"))
        repository.add(User(identifier="u1"))
        repository.add(Asset(identifier="g1"))
        host_service = HostInventoryService(repository=repository)

        hosts = host_service.list_hosts()

        assert len(hosts) == 2
        assert all(isinstance(h, Host) for h in hosts)

    def test_list_hosts_empty_when_none_registered(
        self, host_service: HostInventoryService
    ) -> None:
        assert host_service.list_hosts() == []


class TestUserInventoryService:
    def test_register_user_returns_saved_user(self, user_service: UserInventoryService) -> None:
        user = User(identifier="jdoe", is_privileged=True)

        saved = user_service.register_user(user)

        assert isinstance(saved, User)
        assert saved.is_privileged is True

    def test_register_duplicate_identifier_rejected(
        self, user_service: UserInventoryService
    ) -> None:
        user_service.register_user(User(identifier="dup-user"))

        with pytest.raises(DuplicateAssetError):
            user_service.register_user(User(identifier="dup-user"))

    def test_get_user_returns_none_for_missing_id(self, user_service: UserInventoryService) -> None:
        assert user_service.get_user(uuid.uuid4()) is None

    def test_get_user_returns_none_for_non_user_asset(self) -> None:
        repository = FakeAssetRepository()
        host = repository.add(Host(identifier="not-a-user"))
        user_service = UserInventoryService(repository=repository)

        assert user_service.get_user(host.id) is None

    def test_get_user_returns_the_user(self, user_service: UserInventoryService) -> None:
        saved = user_service.register_user(User(identifier="asmith"))

        fetched = user_service.get_user(saved.id)

        assert fetched is not None
        assert fetched.id == saved.id

    def test_list_users_returns_only_users(self) -> None:
        repository = FakeAssetRepository()
        repository.add(User(identifier="u1"))
        repository.add(User(identifier="u2"))
        repository.add(Host(identifier="h1"))
        user_service = UserInventoryService(repository=repository)

        users = user_service.list_users()

        assert len(users) == 2
        assert all(isinstance(u, User) for u in users)

    def test_list_users_empty_when_none_registered(
        self, user_service: UserInventoryService
    ) -> None:
        assert user_service.list_users() == []


class TestCrossTypeIsolation:
    """Hosts and users sharing one repository never leak into each other's
    type-scoped view."""

    def test_hosts_and_users_are_independently_visible(self) -> None:
        repository = FakeAssetRepository()
        repository.add(Host(identifier="h1"))
        repository.add(User(identifier="u1"))
        host_service = HostInventoryService(repository=repository)
        user_service = UserInventoryService(repository=repository)

        assert len(host_service.list_hosts()) == 1
        assert len(user_service.list_users()) == 1
