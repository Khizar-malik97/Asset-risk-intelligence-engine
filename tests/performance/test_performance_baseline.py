"""Performance baseline (Milestone 23).

Establishes documented timing baselines for the operations most likely
to degrade as the inventory grows: bulk registration, filtered search,
export, and per-asset risk scoring. The numbers this file measures are
also what scripts/run_performance_baseline.py writes into
docs/performance_baseline.md — that script/doc pair is the source of
truth for "what does this machine actually measure"; the assertions
below are deliberately generous (well above the sandbox baseline the
docs record) so this suite catches a genuine N+1-style regression
without flaking on a slower CI runner or a different developer's laptop.

Excluded from the default `pytest` run (see pyproject.toml's
`addopts`/`markers`) — these move real rows through a real database and
are meaningfully slower than the rest of the suite. Run explicitly:
    pytest -m performance -v -s
The `-s` flag matters: these tests print their own timing report, and
pytest hides print() output by default.
"""

import time
from collections.abc import Generator
from datetime import UTC, datetime
from statistics import mean, median

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from api.dependencies import get_session
from api.main import app
from models.enums import AssetCategory, DiscoverySource
from models.orm.asset_orm import HostORM
from models.orm.base import Base

pytestmark = pytest.mark.performance

BULK_ASSET_COUNT = 500
API_REGISTRATION_COUNT = 200

# Generous ceilings — see module docstring for why these aren't tight SLAs.
MAX_BULK_INSERT_SECONDS = 5.0
MAX_API_REGISTRATION_SECONDS = 10.0
MAX_LIST_ALL_SECONDS = 1.0
MAX_FILTERED_SEARCH_SECONDS = 1.0
MAX_EXPORT_SECONDS = 1.0
MAX_SINGLE_RISK_SCORE_SECONDS = 0.1


@pytest.fixture
def db_engine() -> Generator[Engine, None, None]:
    """The single shared engine backing both the TestClient (via a
    dependency override) and this file's direct bulk-seeding helper —
    same StaticPool/check_same_thread setup as every other integration
    test's fixture, for the same reason (see test_api_assets.py)."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine


@pytest.fixture
def client(db_engine: Engine) -> Generator[TestClient, None, None]:
    testing_session_local = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)

    def override_get_session() -> Generator[Session, None, None]:
        session = testing_session_local()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _seed_bulk_hosts(db_engine: Engine, count: int) -> float:
    """Insert `count` hosts directly at the ORM layer, against the SAME
    engine the API's dependency override uses — bypassing the API/HTTP
    stack entirely so this measures raw persistence speed, not request
    overhead. Returns elapsed seconds for one session, `count` adds, one
    commit."""
    session_factory = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)
    session = session_factory()
    started = time.perf_counter()
    try:
        for i in range(count):
            session.add(
                HostORM(
                    identifier=f"perf-host-{i:05d}",
                    category=AssetCategory.SERVER if i % 2 == 0 else AssetCategory.WORKSTATION,
                    is_critical=(i % 10 == 0),
                    discovery_source=DiscoverySource.MANUAL,
                    first_seen=datetime.now(UTC),
                    last_seen=datetime.now(UTC),
                    ip_address=f"10.0.{i // 256}.{i % 256}",
                    is_internet_facing=(i % 3 == 0),
                )
            )
        session.commit()
    finally:
        session.close()
    return time.perf_counter() - started


class TestBulkInsertBaseline:
    def test_bulk_insert_of_500_assets_completes_within_ceiling(self, db_engine: Engine) -> None:
        elapsed = _seed_bulk_hosts(db_engine, BULK_ASSET_COUNT)

        print(f"\n[perf] bulk-insert {BULK_ASSET_COUNT} hosts (ORM, one commit): {elapsed:.3f}s")
        assert elapsed < MAX_BULK_INSERT_SECONDS


class TestApiRegistrationBaseline:
    def test_registering_200_assets_through_the_real_api(self, client: TestClient) -> None:
        """Exercises the full stack per asset: HTTP -> Pydantic validation
        -> InventoryService.register_asset() (which itself runs a
        duplicate-identifier lookup query) -> commit. This is the
        realistic cost of onboarding assets one at a time through the API,
        as a human or an integration would actually do it."""
        durations: list[float] = []
        for i in range(API_REGISTRATION_COUNT):
            started = time.perf_counter()
            response = client.post("/assets", json={"identifier": f"api-perf-{i:05d}"})
            durations.append(time.perf_counter() - started)
            assert response.status_code == 201

        total = sum(durations)
        print(
            f"\n[perf] register {API_REGISTRATION_COUNT} assets via API: "
            f"total={total:.3f}s mean={mean(durations) * 1000:.2f}ms "
            f"median={median(durations) * 1000:.2f}ms max={max(durations) * 1000:.2f}ms"
        )
        assert total < MAX_API_REGISTRATION_SECONDS


class TestReadPathBaseline:
    def test_list_all_assets_at_scale(self, client: TestClient, db_engine: Engine) -> None:
        _seed_bulk_hosts(db_engine, BULK_ASSET_COUNT)

        started = time.perf_counter()
        response = client.get("/assets")
        elapsed = time.perf_counter() - started

        assert response.status_code == 200
        assert len(response.json()) == BULK_ASSET_COUNT
        print(f"\n[perf] GET /assets ({BULK_ASSET_COUNT} rows, no filter): {elapsed * 1000:.2f}ms")
        assert elapsed < MAX_LIST_ALL_SECONDS

    def test_combined_filter_search_at_scale(self, client: TestClient, db_engine: Engine) -> None:
        """Proves the SQL-pushed-down filters (Milestone 18) actually
        keep this fast at volume — the whole reason that milestone
        overrode the interface's naive Python-side default."""
        _seed_bulk_hosts(db_engine, BULK_ASSET_COUNT)

        started = time.perf_counter()
        response = client.get(
            "/assets",
            params={"category": "server", "is_critical": True, "text": "perf-host"},
        )
        elapsed = time.perf_counter() - started

        assert response.status_code == 200
        print(
            f"\n[perf] GET /assets?category&is_critical&text ({BULK_ASSET_COUNT} rows): "
            f"{elapsed * 1000:.2f}ms, {len(response.json())} matched"
        )
        assert elapsed < MAX_FILTERED_SEARCH_SECONDS

    def test_export_at_scale(self, client: TestClient, db_engine: Engine) -> None:
        _seed_bulk_hosts(db_engine, BULK_ASSET_COUNT)

        started = time.perf_counter()
        response = client.get("/export/assets")
        elapsed = time.perf_counter() - started

        assert response.status_code == 200
        assert response.json()["asset_count"] == BULK_ASSET_COUNT
        print(f"\n[perf] GET /export/assets ({BULK_ASSET_COUNT} rows): {elapsed * 1000:.2f}ms")
        assert elapsed < MAX_EXPORT_SECONDS


class TestRiskScoringBaseline:
    def test_single_asset_risk_score_latency(self, client: TestClient) -> None:
        """Risk scoring runs registered factors in Python per request
        (Milestone 13) rather than in SQL — this is the operation most
        exposed to getting slow as more factors get added later."""
        created = client.post(
            "/assets/hosts",
            json={
                "identifier": "perf-risk-01",
                "category": "server",
                "is_internet_facing": True,
            },
        ).json()
        asset_id = created["id"]
        client.put(f"/assets/{asset_id}/critical")
        client.post(
            f"/assets/{asset_id}/exposure-signals",
            json={
                "signal_type": "internet_facing",
                "severity": "high",
                "description": "Publicly reachable",
            },
        )

        started = time.perf_counter()
        response = client.get(f"/assets/{asset_id}/risk")
        elapsed = time.perf_counter() - started

        assert response.status_code == 200
        print(f"\n[perf] GET /assets/{{id}}/risk (1 asset, 1 signal): {elapsed * 1000:.2f}ms")
        assert elapsed < MAX_SINGLE_RISK_SCORE_SECONDS
