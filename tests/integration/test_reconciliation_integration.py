"""Integration test: DiscoveryService produces duplicates, ReconciliationService
cleans them up — against a real SQLAlchemyAssetRepository, proving the full
Discovery -> Reconciliation pipeline works end to end.
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
from services.discovery.reconciliation import ReconciliationService


@pytest.fixture()
def repository() -> Generator[SQLAlchemyAssetRepository, None, None]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield SQLAlchemyAssetRepository(session)


def test_discovery_then_reconciliation_leaves_one_record_per_asset(
    repository: SQLAlchemyAssetRepository,
) -> None:
    provider_a = StaticDiscoveryProvider(
        name="feed-a", assets=[Asset(identifier="shared-01"), Asset(identifier="unique-a")]
    )
    provider_b = StaticDiscoveryProvider(
        name="feed-b", assets=[Asset(identifier="shared-01"), Asset(identifier="unique-b")]
    )
    discovery_service = DiscoveryService(providers=[provider_a, provider_b], repository=repository)
    discovery_service.run_discovery()

    # Before reconciliation: 4 rows (shared-01 appears twice).
    assert len(repository.list_all()) == 4

    reconciliation_service = ReconciliationService(repository)
    result = reconciliation_service.reconcile_all()

    assert result.total_duplicates_removed == 1
    remaining = repository.list_all()
    assert len(remaining) == 3
    identifiers = {a.identifier for a in remaining}
    assert identifiers == {"shared-01", "unique-a", "unique-b"}


def test_critical_flag_survives_reconciliation_through_real_database(
    repository: SQLAlchemyAssetRepository,
) -> None:
    critical_asset = Asset(identifier="crit-shared", is_critical=True)
    non_critical_asset = Asset(identifier="crit-shared", is_critical=False)

    provider_older = StaticDiscoveryProvider(name="feed-old", assets=[critical_asset])
    provider_newer = StaticDiscoveryProvider(name="feed-new", assets=[non_critical_asset])

    # Run the "older" critical observation first, then the "newer" non-critical one.
    DiscoveryService(providers=[provider_older], repository=repository).run_discovery()
    DiscoveryService(providers=[provider_newer], repository=repository).run_discovery()

    reconciliation_service = ReconciliationService(repository)
    reconciliation_service.reconcile_all()

    remaining = repository.list_all()
    matches = [a for a in remaining if a.identifier == "crit-shared"]
    assert len(matches) == 1
    assert matches[0].is_critical is True
