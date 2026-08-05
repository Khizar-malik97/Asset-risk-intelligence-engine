"""Integration test: AssetInventoryService backed by the REAL
SQLAlchemyAssetRepository against an in-memory SQLite database.

This is the first test that exercises the entire stack built so far —
service -> repository -> mapper -> ORM -> database — end to end.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from models.enums import AssetCategory
from models.host import Host
from models.orm.base import Base
from repositories.asset_repository import SQLAlchemyAssetRepository
from services.exceptions import DuplicateAssetError
from services.inventory.inventory_service import AssetInventoryService


@pytest.fixture()
def service():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        repository = SQLAlchemyAssetRepository(session)
        yield AssetInventoryService(repository=repository)


def test_full_lifecycle_through_real_database(service):
    """register -> get -> update -> delete, all through real persistence."""
    host = Host(identifier="prod-web-01", ip_address="10.1.1.1")

    registered = service.register_asset(host)
    assert registered.id == host.id

    fetched = service.get_asset(host.id)
    assert fetched is not None
    assert fetched.ip_address == "10.1.1.1"

    fetched.ip_address = "10.1.1.2"
    updated = service.update_asset(fetched)
    assert updated.ip_address == "10.1.1.2"

    service.delete_asset(host.id)
    assert service.get_asset(host.id) is None


def test_list_assets_through_real_database(service):
    service.register_asset(Host(identifier="h1"))
    service.register_asset(Host(identifier="h2"))

    all_assets = service.list_assets()

    assert len(all_assets) == 2


def test_duplicate_identifier_rejected_through_real_database(service):
    service.register_asset(Host(identifier="dup-prod-01"))

    with pytest.raises(DuplicateAssetError):
        service.register_asset(Host(identifier="dup-prod-01"))

    # Confirm the rejected duplicate never made it to the database.
    all_assets = service.list_assets()
    assert len(all_assets) == 1


def test_critical_flagging_through_real_database(service):
    critical_host = service.register_asset(Host(identifier="dc-01"))
    service.register_asset(Host(identifier="workstation-01"))

    service.flag_as_critical(critical_host.id)

    critical_assets = service.list_critical_assets()
    assert len(critical_assets) == 1
    assert critical_assets[0].id == critical_host.id

    service.unflag_as_critical(critical_host.id)
    assert service.list_critical_assets() == []


def test_category_assignment_through_real_database(service):
    db_host = service.register_asset(Host(identifier="db-01"))
    service.register_asset(Host(identifier="ws-01"))

    service.assign_category(db_host.id, AssetCategory.DATABASE_SERVER)

    matching = service.list_assets_by_category(AssetCategory.DATABASE_SERVER)
    assert len(matching) == 1
    assert matching[0].id == db_host.id
