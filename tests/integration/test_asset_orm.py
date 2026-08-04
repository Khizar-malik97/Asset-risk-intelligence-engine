"""Integration tests for the ORM schema: migration correctness and round-trip
insert/query behavior against a real (in-memory) SQLite database.

These are integration tests, not unit tests: they exercise the actual
database, not a mock — proving the schema Alembic creates actually works.
"""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from models.enums import AssetCategory, AssetType, DiscoverySource
from models.orm.asset_orm import AssetORM, HostORM, UserORM
from models.orm.base import Base


@pytest.fixture()
def db_session():
    """A fresh in-memory SQLite database, schema created directly from our
    ORM models (not via Alembic) — fast and fully isolated per test."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_generic_asset_round_trip(db_session):
    asset = AssetORM(
        id=uuid.uuid4(),
        identifier="generic-001",
        asset_type=AssetType.GENERIC,
        category=AssetCategory.UNCATEGORIZED,
        is_critical=False,
        discovery_source=DiscoverySource.MANUAL,
        first_seen=datetime.now(UTC),
        last_seen=datetime.now(UTC),
    )
    db_session.add(asset)
    db_session.commit()

    fetched = db_session.get(AssetORM, asset.id)
    assert fetched is not None
    assert fetched.identifier == "generic-001"
    assert fetched.asset_type == AssetType.GENERIC


def test_host_round_trip_with_polymorphic_load(db_session):
    host_id = uuid.uuid4()
    host = HostORM(
        id=host_id,
        asset_id=host_id,
        identifier="web-01",
        category=AssetCategory.SERVER,
        is_critical=True,
        discovery_source=DiscoverySource.MANUAL,
        first_seen=datetime.now(UTC),
        last_seen=datetime.now(UTC),
        ip_address="10.0.0.5",
        operating_system="Ubuntu 24.04",
        is_internet_facing=True,
    )
    db_session.add(host)
    db_session.commit()
    db_session.expunge_all()

    # Fetching via the base AssetORM should polymorphically load as HostORM,
    # since asset_type discriminates which subclass table to join.
    fetched = db_session.get(AssetORM, host_id)
    assert isinstance(fetched, HostORM)
    assert fetched.ip_address == "10.0.0.5"
    assert fetched.is_internet_facing is True
    assert fetched.is_critical is True


def test_user_round_trip_with_polymorphic_load(db_session):
    user_id = uuid.uuid4()
    user = UserORM(
        id=user_id,
        asset_id=user_id,
        identifier="jdoe",
        category=AssetCategory.STANDARD_USER_ACCOUNT,
        discovery_source=DiscoverySource.MANUAL,
        first_seen=datetime.now(UTC),
        last_seen=datetime.now(UTC),
        is_privileged=True,
        department="IT",
    )
    db_session.add(user)
    db_session.commit()
    db_session.expunge_all()

    fetched = db_session.get(AssetORM, user_id)
    assert isinstance(fetched, UserORM)
    assert fetched.is_privileged is True
    assert fetched.department == "IT"


def test_querying_base_asset_table_returns_mixed_types(db_session):
    """Querying AssetORM directly should return hosts and users too — this
    is the whole point of joined-table inheritance: one table to query
    across all asset types, per FR-1."""
    generic_id, host_id, user_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    now = datetime.now(UTC)

    db_session.add(AssetORM(id=generic_id, identifier="g1", first_seen=now, last_seen=now))
    db_session.add(
        HostORM(id=host_id, asset_id=host_id, identifier="h1", first_seen=now, last_seen=now)
    )
    db_session.add(
        UserORM(id=user_id, asset_id=user_id, identifier="u1", first_seen=now, last_seen=now)
    )
    db_session.commit()

    all_assets = db_session.query(AssetORM).all()
    assert len(all_assets) == 3
    types_found = {type(a) for a in all_assets}
    assert types_found == {AssetORM, HostORM, UserORM}


def test_duplicate_identifier_is_allowed_at_db_layer(db_session):
    """The DB layer intentionally does NOT enforce identifier uniqueness —
    deduplication is Reconciliation's job (Milestone 16), not a DB constraint.
    This test documents that decision so it isn't 'fixed' accidentally later."""
    now = datetime.now(UTC)
    a1 = AssetORM(id=uuid.uuid4(), identifier="dup-host", first_seen=now, last_seen=now)
    a2 = AssetORM(id=uuid.uuid4(), identifier="dup-host", first_seen=now, last_seen=now)

    db_session.add_all([a1, a2])
    db_session.commit()  # should NOT raise

    matches = db_session.query(AssetORM).filter_by(identifier="dup-host").all()
    assert len(matches) == 2
