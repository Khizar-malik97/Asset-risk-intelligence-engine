"""Integration tests for the JSON export endpoint through the real API,
real database, and real ExportService/AssetSearchService wiring."""

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


class TestExportEndpoint:
    def test_export_with_no_assets_is_an_empty_document(self, client: TestClient) -> None:
        response = client.get("/export/assets")

        assert response.status_code == 200
        body = response.json()
        assert body["asset_count"] == 0
        assert body["assets"] == []
        assert body["schema_version"] == 1
        assert "exported_at" in body

    def test_export_includes_every_registered_asset(self, client: TestClient) -> None:
        client.post("/assets", json={"identifier": "export-a"})
        client.post("/assets", json={"identifier": "export-b"})

        response = client.get("/export/assets")

        body = response.json()
        assert body["asset_count"] == 2
        assert {a["identifier"] for a in body["assets"]} == {"export-a", "export-b"}

    def test_export_filters_by_category(self, client: TestClient) -> None:
        client.post(
            "/assets/hosts", json={"identifier": "db-export-01", "category": "database_server"}
        )
        client.post("/assets", json={"identifier": "uncategorized-01"})

        response = client.get("/export/assets", params={"category": "database_server"})

        body = response.json()
        assert body["asset_count"] == 1
        assert body["assets"][0]["identifier"] == "db-export-01"

    def test_export_filters_by_criticality(self, client: TestClient) -> None:
        created = client.post("/assets", json={"identifier": "crit-export-01"}).json()
        client.put(f"/assets/{created['id']}/critical")
        client.post("/assets", json={"identifier": "normal-export-01"})

        response = client.get("/export/assets", params={"is_critical": True})

        body = response.json()
        assert body["asset_count"] == 1
        assert body["assets"][0]["identifier"] == "crit-export-01"

    def test_export_matches_documented_schema_shape(self, client: TestClient) -> None:
        client.post(
            "/assets/hosts",
            json={"identifier": "shape-export-01", "ip_address": "10.1.1.1"},
        )

        response = client.get("/export/assets")

        exported = response.json()["assets"][0]
        expected_keys = {
            "id",
            "identifier",
            "asset_type",
            "category",
            "is_critical",
            "discovery_source",
            "first_seen",
            "last_seen",
            "ip_address",
            "operating_system",
            "is_internet_facing",
            "is_privileged",
            "department",
        }
        assert set(exported.keys()) == expected_keys
        assert exported["ip_address"] == "10.1.1.1"
