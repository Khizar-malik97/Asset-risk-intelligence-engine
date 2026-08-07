"""Integration tests for the discovery-related API endpoints.

Same in-memory-DB pattern as test_api_assets.py, plus an override for
get_discovery_providers() — the default (empty list, see
api/dependencies.py) is correct for production but useless for testing
that a real provider's results actually flow through the API, so tests
that need real discovered assets override it with a StaticDiscoveryProvider.
"""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from api.dependencies import get_discovery_providers, get_session
from api.main import app
from models.host import Host
from models.orm.base import Base
from services.discovery.providers.static_provider import StaticDiscoveryProvider


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    # See test_api_assets.py's client fixture for why StaticPool is required
    # (not optional) here — without it, the tables created below are
    # invisible to the worker thread that actually handles each request.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    testing_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)

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


class TestDiscoveryRun:
    def test_run_with_no_providers_returns_empty_result(self, client: TestClient) -> None:
        response = client.post("/discovery/run")

        assert response.status_code == 200
        body = response.json()
        assert body["assets"] == []
        assert body["assets_by_provider"] == {}

    def test_run_with_a_configured_provider_persists_assets(self, client: TestClient) -> None:
        provider = StaticDiscoveryProvider(
            name="test-agent-feed",
            assets=[Host(identifier="discovered-01"), Host(identifier="discovered-02")],
        )

        def override_providers() -> list[StaticDiscoveryProvider]:
            return [provider]

        app.dependency_overrides[get_discovery_providers] = override_providers
        try:
            response = client.post("/discovery/run")
        finally:
            del app.dependency_overrides[get_discovery_providers]

        assert response.status_code == 200
        body = response.json()
        assert len(body["assets"]) == 2
        assert body["assets_by_provider"] == {"test-agent-feed": 2}
        assert all(a["discovery_source"] == "discovery_provider" for a in body["assets"])


class TestReconciliation:
    def test_reconcile_with_no_duplicates_is_a_noop(self, client: TestClient) -> None:
        client.post("/assets", json={"identifier": "unique-01"})

        response = client.post("/discovery/reconcile")

        assert response.status_code == 200
        body = response.json()
        assert body["groups_reconciled"] == []
        assert body["total_duplicates_removed"] == 0

    def test_reconcile_merges_duplicates_from_discovery(self, client: TestClient) -> None:
        provider = StaticDiscoveryProvider(
            name="dup-feed",
            assets=[Host(identifier="dup-host"), Host(identifier="dup-host")],
        )

        def override_providers() -> list[StaticDiscoveryProvider]:
            return [provider]

        app.dependency_overrides[get_discovery_providers] = override_providers
        try:
            client.post("/discovery/run")
            response = client.post("/discovery/reconcile")
        finally:
            del app.dependency_overrides[get_discovery_providers]

        assert response.status_code == 200
        body = response.json()
        assert body["total_duplicates_removed"] == 1
        assert len(body["groups_reconciled"]) == 1
        assert body["groups_reconciled"][0]["identifier"] == "dup-host"

        list_response = client.get("/assets")
        assert len(list_response.json()) == 1
