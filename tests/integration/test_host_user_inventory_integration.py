"""Integration test: HostInventoryService and UserInventoryService against a
real SQLAlchemyAssetRepository — proving list_hosts()/list_users() (added to
the repository this milestone) query correctly against real joined-table
inheritance, not just the fake repository's isinstance() shortcut.
"""

from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from models.asset import Asset
from models.host import Host
from models.orm.base import Base
from models.user import User
from repositories.asset_repository import SQLAlchemyAssetRepository
from services.inventory.host_inventory_service import HostInventoryService
from services.inventory.user_inventory_service import UserInventoryService


@pytest.fixture()
def repository() -> Generator[SQLAlchemyAssetRepository, None, None]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield SQLAlchemyAssetRepository(session)


def test_host_and_user_services_against_real_database(
    repository: SQLAlchemyAssetRepository,
) -> None:
    host_service = HostInventoryService(repository=repository)
    user_service = UserInventoryService(repository=repository)

    host_service.register_host(Host(identifier="db-web-01", ip_address="10.5.5.5"))
    host_service.register_host(Host(identifier="db-web-02"))
    user_service.register_user(User(identifier="db-jdoe", is_privileged=True))
    repository.add(Asset(identifier="db-generic-01"))  # neither host nor user

    hosts = host_service.list_hosts()
    users = user_service.list_users()

    assert len(hosts) == 2
    assert all(isinstance(h, Host) for h in hosts)
    assert len(users) == 1
    assert users[0].is_privileged is True

    # The generic asset shows up in neither type-scoped view.
    assert len(repository.list_all()) == 4
