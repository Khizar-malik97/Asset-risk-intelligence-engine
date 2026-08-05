"""Integration tests for SQLAlchemyAssetRepository.

These run against a real (in-memory) SQLite database via the actual
repository class — proving the repository, the mapper, and the ORM schema
all work together correctly, not just in isolation.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from models.asset import Asset
from models.enums import AssetCategory
from models.host import Host
from models.orm.base import Base
from models.user import User
from repositories.asset_repository import SQLAlchemyAssetRepository
from repositories.exceptions import AssetNotFoundError


@pytest.fixture()
def repository():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield SQLAlchemyAssetRepository(session)


class TestAdd:
    def test_add_generic_asset(self, repository):
        asset = Asset(identifier="generic-001")

        saved = repository.add(asset)

        assert saved.id == asset.id
        assert saved.identifier == "generic-001"

    def test_add_host(self, repository):
        host = Host(identifier="web-01", ip_address="10.0.0.5", is_internet_facing=True)

        saved = repository.add(host)

        assert isinstance(saved, Host)
        assert saved.ip_address == "10.0.0.5"
        assert saved.is_internet_facing is True

    def test_add_user(self, repository):
        user = User(identifier="jdoe", is_privileged=True, department="IT")

        saved = repository.add(user)

        assert isinstance(saved, User)
        assert saved.is_privileged is True
        assert saved.department == "IT"


class TestGetById:
    def test_get_existing_asset(self, repository):
        host = repository.add(Host(identifier="web-02"))

        fetched = repository.get_by_id(host.id)

        assert fetched is not None
        assert fetched.id == host.id
        assert isinstance(fetched, Host)

    def test_get_nonexistent_returns_none(self, repository):
        import uuid

        result = repository.get_by_id(uuid.uuid4())

        assert result is None


class TestGetByIdentifier:
    def test_get_existing_by_identifier(self, repository):
        repository.add(Host(identifier="unique-host"))

        fetched = repository.get_by_identifier("unique-host")

        assert fetched is not None
        assert fetched.identifier == "unique-host"

    def test_get_nonexistent_identifier_returns_none(self, repository):
        result = repository.get_by_identifier("does-not-exist")

        assert result is None

    def test_identifier_lookup_is_case_sensitive(self, repository):
        repository.add(Host(identifier="CaseSensitive"))

        assert repository.get_by_identifier("casesensitive") is None
        assert repository.get_by_identifier("CaseSensitive") is not None


class TestListAll:
    def test_list_all_returns_mixed_types(self, repository):
        repository.add(Asset(identifier="g1"))
        repository.add(Host(identifier="h1"))
        repository.add(User(identifier="u1"))

        all_assets = repository.list_all()

        assert len(all_assets) == 3
        types_found = {type(a) for a in all_assets}
        assert types_found == {Asset, Host, User}

    def test_list_all_on_empty_repository(self, repository):
        assert repository.list_all() == []


class TestListCritical:
    def test_returns_only_critical_flagged(self, repository):
        critical = repository.add(Host(identifier="dc-01", is_critical=True))
        repository.add(Host(identifier="ws-01", is_critical=False))

        result = repository.list_critical()

        assert len(result) == 1
        assert result[0].id == critical.id

    def test_empty_when_nothing_flagged(self, repository):
        repository.add(Host(identifier="ws-02"))

        assert repository.list_critical() == []


class TestListByCategory:
    def test_returns_only_matching_category(self, repository):
        db_server = repository.add(Host(identifier="db-01", category=AssetCategory.DATABASE_SERVER))
        repository.add(Host(identifier="ws-03", category=AssetCategory.WORKSTATION))

        result = repository.list_by_category(AssetCategory.DATABASE_SERVER)

        assert len(result) == 1
        assert result[0].id == db_server.id

    def test_empty_when_no_match(self, repository):
        repository.add(Host(identifier="ws-04", category=AssetCategory.WORKSTATION))

        assert repository.list_by_category(AssetCategory.NETWORK_DEVICE) == []


class TestUpdate:
    def test_update_existing_asset(self, repository):
        host = repository.add(Host(identifier="web-03", ip_address="10.0.0.1"))

        host.ip_address = "10.0.0.2"
        host.category = AssetCategory.SERVER
        updated = repository.update(host)

        assert updated.ip_address == "10.0.0.2"
        assert updated.category == AssetCategory.SERVER

        refetched = repository.get_by_id(host.id)
        assert refetched.ip_address == "10.0.0.2"

    def test_update_nonexistent_raises(self, repository):
        phantom = Host(identifier="ghost")

        with pytest.raises(AssetNotFoundError):
            repository.update(phantom)


class TestDelete:
    def test_delete_existing_asset(self, repository):
        asset = repository.add(Asset(identifier="to-delete"))

        repository.delete(asset.id)

        assert repository.get_by_id(asset.id) is None

    def test_delete_nonexistent_raises(self, repository):
        import uuid

        with pytest.raises(AssetNotFoundError):
            repository.delete(uuid.uuid4())
