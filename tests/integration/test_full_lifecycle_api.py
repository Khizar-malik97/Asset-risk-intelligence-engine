"""Milestone 22's headline deliverable: full-flow integration scenarios
through the real API, real database, and real services wired together —
register -> discover -> reconcile -> score -> search -> export -> risk
API, in one continuous story, rather than each milestone's feature
proven only in isolation from every other one.

Every prior milestone already has its own focused integration tests
(test_api_assets.py, test_api_discovery.py, test_api_export.py, etc.) —
this file does NOT duplicate those. It proves the pieces compose: an
asset discovered here is the same asset that gets reconciled, scored,
found by search, and shows up in an export, without re-registering it
through each step.
"""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from api.dependencies import get_discovery_providers, get_session
from api.main import app
from models.enums import AssetCategory
from models.host import Host
from models.orm.base import Base
from services.discovery.providers.static_provider import StaticDiscoveryProvider


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


class TestFullAssetLifecycle:
    def test_manual_registration_through_search_and_export(self, client: TestClient) -> None:
        """Story: a SOC analyst manually registers a critical, internet-
        facing host, flags it critical, attaches an exposure signal,
        confirms its risk score reflects both factors, finds it via
        search, and confirms it appears correctly in an export — all
        against the SAME asset id throughout."""
        # 1. Register
        created = client.post(
            "/assets/hosts",
            json={
                "identifier": "lifecycle-web-01",
                "category": "server",
                "ip_address": "203.0.113.10",
                "is_internet_facing": True,
            },
        ).json()
        asset_id = created["id"]
        assert created["category"] == "server"

        # 2. Flag critical
        flagged = client.put(f"/assets/{asset_id}/critical").json()
        assert flagged["is_critical"] is True

        # 3. Attach an exposure signal
        signal = client.post(
            f"/assets/{asset_id}/exposure-signals",
            json={
                "signal_type": "internet_facing",
                "severity": "high",
                "description": "Publicly reachable on port 443",
            },
        ).json()
        assert signal["asset_id"] == asset_id

        # 4. Risk score reflects BOTH the critical flag and the signal
        risk = client.get(f"/assets/{asset_id}/risk").json()
        assert risk["total_score"] == 30 + 25  # critical_asset_flag + internet_facing
        assert risk["risk_level"] == "high"
        triggered_factors = {f["factor_name"] for f in risk["factor_results"] if f["triggered"]}
        assert triggered_factors == {"critical_asset_flag", "internet_facing"}

        # 5. Confidence score is independently queryable for the same asset
        confidence = client.get(f"/assets/{asset_id}/confidence").json()
        assert confidence["asset_id"] == asset_id

        # 6. Findable via search using the risk level just proven above
        search_results = client.get(
            "/assets", params={"category": "server", "risk_level": "high"}
        ).json()
        assert asset_id in {a["id"] for a in search_results}

        # 7. Appears correctly in an export filtered the same way
        export = client.get(
            "/export/assets", params={"category": "server", "is_critical": True}
        ).json()
        exported_ids = {a["id"] for a in export["assets"]}
        assert asset_id in exported_ids
        exported_asset = next(a for a in export["assets"] if a["id"] == asset_id)
        assert exported_asset["ip_address"] == "203.0.113.10"
        assert exported_asset["is_internet_facing"] is True

    def test_discovery_through_reconciliation_to_export(self, client: TestClient) -> None:
        """Story: two discovery providers report overlapping views of the
        same real-world host (one sees it privileged/internet-facing —
        current AXERONIX terminology — the other doesn't); discovery
        persists both as separate rows, reconciliation merges them into
        one canonical record, and that canonical record — not either
        duplicate — is what search and export both see afterward."""
        provider_a = StaticDiscoveryProvider(
            name="agent-feed",
            assets=[Host(identifier="dup-host-01", category=AssetCategory.SERVER)],
        )
        provider_b = StaticDiscoveryProvider(
            name="scanner-feed",
            assets=[
                Host(
                    identifier="dup-host-01",
                    category=AssetCategory.SERVER,
                    is_internet_facing=True,
                )
            ],
        )

        def override_providers() -> list[StaticDiscoveryProvider]:
            return [provider_a, provider_b]

        app.dependency_overrides[get_discovery_providers] = override_providers
        try:
            # 1. Discover — persists two rows sharing one identifier
            discovery_result = client.post("/discovery/run").json()
            assert discovery_result["assets_by_provider"] == {
                "agent-feed": 1,
                "scanner-feed": 1,
            }

            all_before = client.get("/assets").json()
            assert sum(1 for a in all_before if a["identifier"] == "dup-host-01") == 2

            # 2. Reconcile — merges the duplicate pair into one
            reconciliation_result = client.post("/discovery/reconcile").json()
            assert reconciliation_result["total_duplicates_removed"] == 1
            canonical_id = reconciliation_result["groups_reconciled"][0]["canonical_asset"]["id"]

            # 3. Exactly one row remains, and it's the canonical one
            all_after = client.get("/assets").json()
            matching = [a for a in all_after if a["identifier"] == "dup-host-01"]
            assert len(matching) == 1
            assert matching[0]["id"] == canonical_id

            # 4. Export sees the same single canonical record, not a duplicate
            export = client.get("/export/assets", params={"text": "dup-host"}).json()
            assert export["asset_count"] == 1
            assert export["assets"][0]["id"] == canonical_id
        finally:
            app.dependency_overrides.pop(get_discovery_providers, None)

    def test_deleting_an_asset_removes_it_from_search_and_export(self, client: TestClient) -> None:
        """Closes the loop the other direction: an asset that's been
        found via search and included in an export must NOT still appear
        in either after being deleted."""
        created = client.post("/assets", json={"identifier": "lifecycle-delete-01"}).json()
        asset_id = created["id"]

        assert asset_id in {
            a["id"] for a in client.get("/assets", params={"text": "lifecycle-delete"}).json()
        }
        assert asset_id in {
            a["id"]
            for a in client.get("/export/assets", params={"text": "lifecycle-delete"}).json()[
                "assets"
            ]
        }

        delete_response = client.delete(f"/assets/{asset_id}")
        assert delete_response.status_code == 204

        assert asset_id not in {
            a["id"] for a in client.get("/assets", params={"text": "lifecycle-delete"}).json()
        }
        assert (
            client.get("/export/assets", params={"text": "lifecycle-delete"}).json()["asset_count"]
            == 0
        )
        assert client.get(f"/assets/{asset_id}").status_code == 404
