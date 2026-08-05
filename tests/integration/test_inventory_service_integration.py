"""Integration test: AssetInventoryService backed by the REAL
SQLAlchemyAssetRepository against an in-memory SQLite database.

This is the first test that exercises the entire stack built so far —
service -> repository -> mapper -> ORM -> database — end to end.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

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
