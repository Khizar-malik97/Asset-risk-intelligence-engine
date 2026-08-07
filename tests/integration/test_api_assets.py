"""Integration tests for the asset-related API endpoints.

Uses FastAPI's TestClient (httpx under the hood) against the real app,
with the database session dependency overridden to an in-memory SQLite
engine — the same "real DB, isolated per test" pattern used by every
other integration test in this suite, just applied through the API layer
instead of calling a service directly.

These tests deliberately do NOT re-verify business rules already proven
at the service layer (e.g. every duplicate-detection edge case) — that
would just be re-testing Milestone 9-18 through a slower, HTTP-shaped
lens. What's actually new and worth testing here is the API's OWN job:
correct status codes, request/response shape, and that dependency wiring
actually connects to a real database.
"""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from api.dependencies import get_session
from api.main import app
from models.orm.base import Base


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    # StaticPool is required here, not optional: FastAPI's TestClient runs
    # endpoint functions in a worker thread (via anyio.to_thread.run_sync),
    # and SQLite's default pooling for :memory: databases hands out ONE
    # connection PER THREAD. Without StaticPool, the tables created below
    # exist only on the test's main-thread connection — the worker thread
    # that actually handles each request sees a separate, empty in-memory
    # database and every query fails with "no such table". StaticPool
    # forces every thread to share the same single connection instead.
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


class TestHealthCheck:
    def test_health_returns_ok(self, client: TestClient) -> None:
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestAssetRegistration:
    def test_register_generic_asset(self, client: TestClient) -> None:
        response = client.post("/assets", json={"identifier": "asset-01"})

        assert response.status_code == 201
        body = response.json()
        assert body["identifier"] == "asset-01"
        assert body["asset_type"] == "generic"

    def test_register_host(self, client: TestClient) -> None:
        response = client.post(
            "/assets/hosts",
            json={
                "identifier": "web-01",
                "ip_address": "10.0.0.5",
                "is_internet_facing": True,
            },
        )

        assert response.status_code == 201
        body = response.json()
        assert body["asset_type"] == "host"
        assert body["ip_address"] == "10.0.0.5"
        assert body["is_internet_facing"] is True

    def test_register_user(self, client: TestClient) -> None:
        response = client.post(
            "/assets/users",
            json={"identifier": "jdoe", "is_privileged": True, "department": "IT"},
        )

        assert response.status_code == 201
        body = response.json()
        assert body["asset_type"] == "user"
        assert body["is_privileged"] is True

    def test_register_duplicate_identifier_returns_409(self, client: TestClient) -> None:
        client.post("/assets", json={"identifier": "dup-01"})

        response = client.post("/assets", json={"identifier": "dup-01"})

        assert response.status_code == 409

    def test_register_blank_identifier_returns_422(self, client: TestClient) -> None:
        response = client.post("/assets", json={"identifier": "   "})

        assert response.status_code == 422

    def test_register_host_invalid_ip_returns_422(self, client: TestClient) -> None:
        response = client.post(
            "/assets/hosts", json={"identifier": "web-02", "ip_address": "not-an-ip"}
        )

        assert response.status_code == 422


class TestAssetRetrieval:
    def test_get_existing_asset(self, client: TestClient) -> None:
        created = client.post("/assets", json={"identifier": "asset-02"}).json()

        response = client.get(f"/assets/{created['id']}")

        assert response.status_code == 200
        assert response.json()["identifier"] == "asset-02"

    def test_get_nonexistent_asset_returns_404(self, client: TestClient) -> None:
        response = client.get("/assets/00000000-0000-0000-0000-000000000000")

        assert response.status_code == 404

    def test_list_all_assets(self, client: TestClient) -> None:
        client.post("/assets", json={"identifier": "a1"})
        client.post("/assets", json={"identifier": "a2"})

        response = client.get("/assets")

        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_delete_existing_asset(self, client: TestClient) -> None:
        created = client.post("/assets", json={"identifier": "to-delete"}).json()

        delete_response = client.delete(f"/assets/{created['id']}")
        get_response = client.get(f"/assets/{created['id']}")

        assert delete_response.status_code == 204
        assert get_response.status_code == 404

    def test_delete_nonexistent_returns_404(self, client: TestClient) -> None:
        response = client.delete("/assets/00000000-0000-0000-0000-000000000000")

        assert response.status_code == 404


class TestSearch:
    def test_search_by_category(self, client: TestClient) -> None:
        client.post("/assets/hosts", json={"identifier": "db-01", "category": "database_server"})
        client.post("/assets/hosts", json={"identifier": "ws-01", "category": "workstation"})

        response = client.get("/assets", params={"category": "database_server"})

        assert response.status_code == 200
        results = response.json()
        assert len(results) == 1
        assert results[0]["identifier"] == "db-01"

    def test_search_by_text(self, client: TestClient) -> None:
        client.post("/assets", json={"identifier": "prod-web-01"})
        client.post("/assets", json={"identifier": "staging-db-01"})

        response = client.get("/assets", params={"text": "web"})

        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_search_by_criticality(self, client: TestClient) -> None:
        created = client.post("/assets", json={"identifier": "crown-jewel"}).json()
        client.put(f"/assets/{created['id']}/critical")
        client.post("/assets", json={"identifier": "not-critical"})

        response = client.get("/assets", params={"is_critical": True})

        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["identifier"] == "crown-jewel"


class TestCriticalityAndCategory:
    def test_flag_and_unflag_critical(self, client: TestClient) -> None:
        created = client.post("/assets", json={"identifier": "flaggable"}).json()

        flagged = client.put(f"/assets/{created['id']}/critical")
        unflagged = client.delete(f"/assets/{created['id']}/critical")

        assert flagged.status_code == 200
        assert flagged.json()["is_critical"] is True
        assert unflagged.status_code == 200
        assert unflagged.json()["is_critical"] is False

    def test_flag_nonexistent_returns_404(self, client: TestClient) -> None:
        response = client.put("/assets/00000000-0000-0000-0000-000000000000/critical")

        assert response.status_code == 404

    def test_assign_category(self, client: TestClient) -> None:
        created = client.post("/assets", json={"identifier": "server-01"}).json()

        response = client.patch(
            f"/assets/{created['id']}/category", json={"category": "database_server"}
        )

        assert response.status_code == 200
        assert response.json()["category"] == "database_server"


class TestExposureSignals:
    def test_attach_and_list_signals(self, client: TestClient) -> None:
        created = client.post("/assets/hosts", json={"identifier": "web-03"}).json()

        attach_response = client.post(
            f"/assets/{created['id']}/exposure-signals",
            json={
                "signal_type": "internet_facing",
                "severity": "high",
                "description": "Publicly reachable on port 443",
            },
        )
        list_response = client.get(f"/assets/{created['id']}/exposure-signals")

        assert attach_response.status_code == 201
        assert list_response.status_code == 200
        assert len(list_response.json()) == 1

    def test_attach_signal_to_nonexistent_asset_returns_404(self, client: TestClient) -> None:
        response = client.post(
            "/assets/00000000-0000-0000-0000-000000000000/exposure-signals",
            json={
                "signal_type": "internet_facing",
                "severity": "high",
                "description": "n/a",
            },
        )

        assert response.status_code == 404

    def test_remove_signal(self, client: TestClient) -> None:
        created = client.post("/assets/hosts", json={"identifier": "web-04"}).json()
        signal = client.post(
            f"/assets/{created['id']}/exposure-signals",
            json={
                "signal_type": "unpatched_vulnerability",
                "severity": "critical",
                "description": "CVE-2024-99999",
            },
        ).json()

        remove_response = client.delete(f"/exposure-signals/{signal['id']}")
        list_response = client.get(f"/assets/{created['id']}/exposure-signals")

        assert remove_response.status_code == 204
        assert list_response.json() == []

    def test_remove_nonexistent_signal_returns_404(self, client: TestClient) -> None:
        response = client.delete("/exposure-signals/00000000-0000-0000-0000-000000000000")

        assert response.status_code == 404


class TestRiskAndConfidence:
    def test_risk_score_for_plain_asset(self, client: TestClient) -> None:
        created = client.post("/assets", json={"identifier": "plain-01"}).json()

        response = client.get(f"/assets/{created['id']}/risk")

        assert response.status_code == 200
        body = response.json()
        assert body["total_score"] == 0
        assert body["risk_level"] == "low"
        assert len(body["factor_results"]) == 4  # all 4 registered factors present

    def test_risk_score_for_critical_asset(self, client: TestClient) -> None:
        created = client.post("/assets", json={"identifier": "critical-01"}).json()
        client.put(f"/assets/{created['id']}/critical")

        response = client.get(f"/assets/{created['id']}/risk")

        assert response.status_code == 200
        assert response.json()["total_score"] == 30  # matches config/risk_weights.yaml
        assert response.json()["risk_level"] == "medium"

    def test_risk_for_nonexistent_asset_returns_404(self, client: TestClient) -> None:
        response = client.get("/assets/00000000-0000-0000-0000-000000000000/risk")

        assert response.status_code == 404

    def test_confidence_score_for_manual_asset(self, client: TestClient) -> None:
        created = client.post("/assets", json={"identifier": "manual-01"}).json()

        response = client.get(f"/assets/{created['id']}/confidence")

        assert response.status_code == 200
        body = response.json()
        assert body["source_reliability_score"] == 100  # manual, just registered
        assert body["confidence_score"] > 0

    def test_confidence_for_nonexistent_asset_returns_404(self, client: TestClient) -> None:
        response = client.get("/assets/00000000-0000-0000-0000-000000000000/confidence")

        assert response.status_code == 404
