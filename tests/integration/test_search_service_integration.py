"""Integration test for AssetSearchService against a real in-memory SQLite
database, using the real SQLAlchemyAssetRepository and
SQLAlchemyExposureSignalRepository together — proves the SQL-pushed-down
search() override and the exposure-signal join both work end-to-end."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from models.enums import AssetCategory, AssetType, DiscoverySource
from models.exposure_signal import ExposureSeverity, ExposureSignal, ExposureSignalType
from models.orm.asset_orm import HostORM
from models.orm.base import Base
from repositories.asset_repository import SQLAlchemyAssetRepository
from repositories.exposure_signal_repository import SQLAlchemyExposureSignalRepository
from services.inventory.search import AssetSearchService


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_search_combines_category_criticality_and_exposure_across_real_database(db_session):
    critical_public_server = HostORM(
        identifier="web-01",
        category=AssetCategory.SERVER,
        is_critical=True,
        discovery_source=DiscoverySource.MANUAL,
        first_seen=datetime.now(UTC),
        last_seen=datetime.now(UTC),
    )
    non_critical_public_server = HostORM(
        identifier="web-02",
        category=AssetCategory.SERVER,
        is_critical=False,
        discovery_source=DiscoverySource.MANUAL,
        first_seen=datetime.now(UTC),
        last_seen=datetime.now(UTC),
    )
    critical_private_workstation = HostORM(
        identifier="ws-01",
        category=AssetCategory.WORKSTATION,
        is_critical=True,
        discovery_source=DiscoverySource.MANUAL,
        first_seen=datetime.now(UTC),
        last_seen=datetime.now(UTC),
    )
    db_session.add_all(
        [critical_public_server, non_critical_public_server, critical_private_workstation]
    )
    db_session.commit()
    for host in (critical_public_server, non_critical_public_server):
        db_session.refresh(host)

    signal_repo = SQLAlchemyExposureSignalRepository(db_session)
    signal_repo.add(
        ExposureSignal(
            asset_id=critical_public_server.id,
            signal_type=ExposureSignalType.INTERNET_FACING,
            severity=ExposureSeverity.HIGH,
            description="Publicly reachable",
        )
    )
    signal_repo.add(
        ExposureSignal(
            asset_id=non_critical_public_server.id,
            signal_type=ExposureSignalType.INTERNET_FACING,
            severity=ExposureSeverity.HIGH,
            description="Publicly reachable",
        )
    )

    asset_repo = SQLAlchemyAssetRepository(db_session)
    search_service = AssetSearchService(asset_repo, signal_repo)

    results = search_service.search(
        category=AssetCategory.SERVER,
        is_critical=True,
        exposure_signal_type=ExposureSignalType.INTERNET_FACING,
    )

    assert [asset.identifier for asset in results] == ["web-01"]


def test_text_search_matches_substring_case_insensitively(db_session):
    db_session.add(
        HostORM(
            identifier="WEB-Production-01",
            category=AssetCategory.SERVER,
            is_critical=False,
            discovery_source=DiscoverySource.MANUAL,
            first_seen=datetime.now(UTC),
            last_seen=datetime.now(UTC),
        )
    )
    db_session.add(
        HostORM(
            identifier="db-prod-01",
            category=AssetCategory.DATABASE_SERVER,
            is_critical=False,
            discovery_source=DiscoverySource.MANUAL,
            first_seen=datetime.now(UTC),
            last_seen=datetime.now(UTC),
        )
    )
    db_session.commit()

    signal_repo = SQLAlchemyExposureSignalRepository(db_session)
    asset_repo = SQLAlchemyAssetRepository(db_session)
    search_service = AssetSearchService(asset_repo, signal_repo)

    results = search_service.search(text="prod")

    assert {asset.identifier for asset in results} == {"WEB-Production-01", "db-prod-01"}


def test_search_filters_by_asset_type_against_real_database(db_session):
    """Closes a real coverage gap: every other filter in
    SQLAlchemyAssetRepository.search() had a DB-backed test; asset_type
    didn't. Uses a generic asset alongside a Host specifically to prove
    the SQL filter distinguishes them, not just that the query runs."""
    from models.orm.asset_orm import AssetORM

    db_session.add(
        AssetORM(
            identifier="generic-01",
            asset_type="generic",
            category=AssetCategory.UNCATEGORIZED,
            is_critical=False,
            discovery_source=DiscoverySource.MANUAL,
            first_seen=datetime.now(UTC),
            last_seen=datetime.now(UTC),
        )
    )
    db_session.add(
        HostORM(
            identifier="host-01",
            category=AssetCategory.SERVER,
            is_critical=False,
            discovery_source=DiscoverySource.MANUAL,
            first_seen=datetime.now(UTC),
            last_seen=datetime.now(UTC),
        )
    )
    db_session.commit()

    signal_repo = SQLAlchemyExposureSignalRepository(db_session)
    asset_repo = SQLAlchemyAssetRepository(db_session)
    search_service = AssetSearchService(asset_repo, signal_repo)

    results = search_service.search(asset_type=AssetType.HOST)

    assert [asset.identifier for asset in results] == ["host-01"]
