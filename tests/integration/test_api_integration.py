"""Integration tests for the Milestone 26 read-only integration API
(/integration/*) through the real API, real database, and real services."""

from collections.abc import Generator
from uuid import uuid4

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


class TestSingleAssetContext:
    def test_returns_lean_context_for_existing_asset(self, client: TestClient) -> None:
        created = client.post("/assets", json={"identifier": "ctx-01", "category": "server"}).json()
        client.put(f"/assets/{created['id']}/critical")

        response = client.get(f"/integration/assets/{created['id']}/context")

        assert response.status_code == 200
        body = response.json()
        assert body["asset_id"] == created["id"]
        assert body["identifier"] == "ctx-01"
        assert body["is_critical"] is True
        assert body["risk_score"] == 30  # critical_asset_flag weight
        assert body["risk_level"] == "medium"
        assert "confidence_score" in body

    def test_returns_standard_404_envelope_for_missing_asset(self, client: TestClient) -> None:
        missing_id = uuid4()

        response = client.get(f"/integration/assets/{missing_id}/context")

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "asset_not_found"


class TestBulkAssetContext:
    def test_returns_context_for_every_found_asset(self, client: TestClient) -> None:
        a = client.post("/assets", json={"identifier": "bulk-a"}).json()
        b = client.post("/assets", json={"identifier": "bulk-b"}).json()

        response = client.post(
            "/integration/assets/context", json={"asset_ids": [a["id"], b["id"]]}
        )

        assert response.status_code == 200
        body = response.json()
        assert {c["asset_id"] for c in body["found"]} == {a["id"], b["id"]}
        assert body["not_found"] == []

    def test_separates_found_from_not_found(self, client: TestClient) -> None:
        found_asset = client.post("/assets", json={"identifier": "bulk-found"}).json()
        missing_id = str(uuid4())

        response = client.post(
            "/integration/assets/context",
            json={"asset_ids": [found_asset["id"], missing_id]},
        )

        body = response.json()
        assert len(body["found"]) == 1
        assert body["found"][0]["asset_id"] == found_asset["id"]
        assert body["not_found"] == [missing_id]

    def test_empty_id_list_rejected(self, client: TestClient) -> None:
        response = client.post("/integration/assets/context", json={"asset_ids": []})

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"


class TestInventorySummary:
    def test_summary_with_empty_inventory(self, client: TestClient) -> None:
        response = client.get("/integration/summary")

        assert response.status_code == 200
        body = response.json()
        assert body["total_assets"] == 0
        assert body["critical_assets"] == 0
        assert body["by_category"] == []
        assert {row["risk_level"] for row in body["by_risk_level"]} == {
            "low",
            "medium",
            "high",
            "critical",
        }
        assert all(row["count"] == 0 for row in body["by_risk_level"])

    def test_summary_reflects_real_counts(self, client: TestClient) -> None:
        client.post("/assets", json={"identifier": "sum-01", "category": "server"})
        client.post("/assets", json={"identifier": "sum-02", "category": "server"})
        critical = client.post(
            "/assets", json={"identifier": "sum-03", "category": "workstation"}
        ).json()
        client.put(f"/assets/{critical['id']}/critical")

        response = client.get("/integration/summary")

        body = response.json()
        assert body["total_assets"] == 3
        assert body["critical_assets"] == 1
        category_counts = {row["category"]: row["count"] for row in body["by_category"]}
        assert category_counts["server"] == 2
        assert category_counts["workstation"] == 1
        risk_counts = {row["risk_level"]: row["count"] for row in body["by_risk_level"]}
        assert risk_counts["medium"] == 1  # the one critical-flagged asset
        assert risk_counts["low"] == 2
