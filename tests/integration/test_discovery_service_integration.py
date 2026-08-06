"""Integration test: DiscoveryService against a real SQLAlchemyAssetRepository,
proving the key architectural contrast with manual registration — discovery
allows duplicate identifiers; manual registration does not.
"""

from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from models.asset import Asset
from models.orm.base import Base
from repositories.asset_repository import SQLAlchemyAssetRepository
from services.discovery.discovery_service import DiscoveryService
from services.discovery.providers.static_provider import StaticDiscoveryProvider
from services.exceptions import DuplicateAssetError
from services.inventory.inventory_service import AssetInventoryService


@pytest.fixture()
def repository() -> Generator[SQLAlchemyAssetRepository, None, None]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield SQLAlchemyAssetRepository(session)


def test_discovery_persists_through_real_database(repository: SQLAlchemyAssetRepository) -> None:
    provider = StaticDiscoveryProvider(
        name="agent-feed", assets=[Asset(identifier="disc-01"), Asset(identifier="disc-02")]
    )
    service = DiscoveryService(providers=[provider], repository=repository)

    result = service.run_discovery()

    assert len(result.assets) == 2
    assert len(repository.list_all()) == 2


def test_discovery_allows_duplicates_manual_registration_rejects_same_identifier(
    repository: SQLAlchemyAssetRepository,
) -> None:
    """The core architectural proof point for this milestone: the SAME
    identifier is accepted twice through Discovery, but the inventory
    service's manual registration path rejects a duplicate outright.

    Uses two separate Asset instances sharing one identifier — each
    discovery observation is a distinct object with its own UUID, the same
    way two independent scans of the same host would produce two separate
    records for reconciliation (Milestone 16) to later merge.
    """
    provider_first_scan = StaticDiscoveryProvider(
        name="agent-feed", assets=[Asset(identifier="shared-host")]
    )
    provider_second_scan = StaticDiscoveryProvider(
        name="agent-feed", assets=[Asset(identifier="shared-host")]
    )
    discovery_service = DiscoveryService(providers=[provider_first_scan], repository=repository)
    discovery_service.run_discovery()

    discovery_service_again = DiscoveryService(
        providers=[provider_second_scan], repository=repository
    )
    discovery_service_again.run_discovery()

    matches = [a for a in repository.list_all() if a.identifier == "shared-host"]
    assert len(matches) == 2

    # Now manual registration of that same identifier: rejected.
    inventory_service = AssetInventoryService(repository=repository)
    with pytest.raises(DuplicateAssetError):
        inventory_service.register_asset(Asset(identifier="shared-host"))
