"""Integration tests for ExposureSignalRepository against a real in-memory DB."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from models.enums import AssetCategory, DiscoverySource
from models.exposure_signal import ExposureSeverity, ExposureSignal, ExposureSignalType
from models.orm.asset_orm import HostORM
from models.orm.base import Base
from repositories.exceptions import ExposureSignalNotFoundError
from repositories.exposure_signal_repository import SQLAlchemyExposureSignalRepository


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def existing_asset_id(db_session):
    """Insert a real Host asset first, since exposure_signals.asset_id is a
    foreign key — signals should always belong to a real asset.

    Uses the actual HostORM subclass (joined-table inheritance) rather than
    the base AssetORM, so SQLAlchemy sets the polymorphic discriminator
    correctly instead of us setting asset_type manually.
    """
    host = HostORM(
        identifier="web-01",
        category=AssetCategory.SERVER,
        is_critical=False,
        discovery_source=DiscoverySource.MANUAL,
        first_seen=datetime.now(UTC),
        last_seen=datetime.now(UTC),
        ip_address="10.2.4.9",
        operating_system="Ubuntu 24.04",
        is_internet_facing=True,
    )
    db_session.add(host)
    db_session.commit()
    db_session.refresh(host)
    return host.id


class TestAdd:
    def test_add_signal(self, db_session, existing_asset_id):
        repo = SQLAlchemyExposureSignalRepository(db_session)
        signal = ExposureSignal(
            asset_id=existing_asset_id,
            signal_type=ExposureSignalType.INTERNET_FACING,
            severity=ExposureSeverity.HIGH,
            description="Publicly reachable on port 443",
        )

        saved = repo.add(signal)

        assert saved.id == signal.id
        assert saved.asset_id == existing_asset_id


class TestListForAsset:
    def test_list_returns_all_signals_for_asset(self, db_session, existing_asset_id):
        repo = SQLAlchemyExposureSignalRepository(db_session)
        repo.add(
            ExposureSignal(
                asset_id=existing_asset_id,
                signal_type=ExposureSignalType.INTERNET_FACING,
                severity=ExposureSeverity.HIGH,
                description="Publicly reachable",
            )
        )
        repo.add(
            ExposureSignal(
                asset_id=existing_asset_id,
                signal_type=ExposureSignalType.UNPATCHED_VULNERABILITY,
                severity=ExposureSeverity.CRITICAL,
                description="CVE-2024-99999 unpatched",
            )
        )

        results = repo.list_for_asset(existing_asset_id)

        assert len(results) == 2

    def test_list_empty_for_asset_with_no_signals(self, db_session, existing_asset_id):
        repo = SQLAlchemyExposureSignalRepository(db_session)

        results = repo.list_for_asset(existing_asset_id)

        assert results == []

    def test_list_does_not_return_other_assets_signals(self, db_session, existing_asset_id):
        repo = SQLAlchemyExposureSignalRepository(db_session)
        repo.add(
            ExposureSignal(
                asset_id=existing_asset_id,
                signal_type=ExposureSignalType.INTERNET_FACING,
                severity=ExposureSeverity.HIGH,
                description="Publicly reachable",
            )
        )

        results = repo.list_for_asset(uuid4())

        assert results == []


class TestRemove:
    def test_remove_existing_signal(self, db_session, existing_asset_id):
        repo = SQLAlchemyExposureSignalRepository(db_session)
        saved = repo.add(
            ExposureSignal(
                asset_id=existing_asset_id,
                signal_type=ExposureSignalType.WEAK_AUTHENTICATION,
                severity=ExposureSeverity.MEDIUM,
                description="Password-only auth, no MFA",
            )
        )

        repo.remove(saved.id)

        assert repo.list_for_asset(existing_asset_id) == []

    def test_remove_nonexistent_raises(self, db_session):
        repo = SQLAlchemyExposureSignalRepository(db_session)

        with pytest.raises(ExposureSignalNotFoundError):
            repo.remove(uuid4())
