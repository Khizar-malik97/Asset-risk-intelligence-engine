"""Integration tests for Milestone 20's standardized error envelope.

Every response body asserted here has the shape:
    {"error": {"code": str, "message": str, "details": dict}}

These tests deliberately don't re-verify the business rule that CAUSES
each error (e.g. "a duplicate identifier is rejected" is already proven
in test_api_assets.py) — they verify the RESPONSE SHAPE is consistent
across every distinct failure mode, which is this milestone's actual job.
"""

from collections.abc import Callable, Generator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from api.dependencies import get_session
from api.main import app
from models.orm.base import Base


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    # See tests/integration/test_api_assets.py's client fixture for why
    # StaticPool + check_same_thread=False are required, not optional,
    # for an in-memory SQLite DB used through FastAPI's TestClient.
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


class TestNotFoundEnvelope:
    def test_asset_not_found_returns_standard_envelope(self, client: TestClient) -> None:
        missing_id = uuid4()

        response = client.get(f"/assets/{missing_id}")

        assert response.status_code == 404
        body = response.json()
        assert body["error"]["code"] == "asset_not_found"
        assert str(missing_id) in body["error"]["message"]
        assert body["error"]["details"] == {"asset_id": str(missing_id)}

    def test_exposure_signal_not_found_returns_standard_envelope(self, client: TestClient) -> None:
        missing_id = uuid4()

        response = client.delete(f"/exposure-signals/{missing_id}")

        assert response.status_code == 404
        body = response.json()
        assert body["error"]["code"] == "exposure_signal_not_found"
        assert body["error"]["details"] == {"signal_id": str(missing_id)}


class TestConflictEnvelope:
    def test_duplicate_asset_returns_standard_envelope(self, client: TestClient) -> None:
        client.post("/assets", json={"identifier": "dup-envelope-01"})

        response = client.post("/assets", json={"identifier": "dup-envelope-01"})

        assert response.status_code == 409
        body = response.json()
        assert body["error"]["code"] == "duplicate_asset"
        assert body["error"]["details"] == {"identifier": "dup-envelope-01"}


class TestValidationEnvelope:
    def test_missing_required_field_returns_standard_envelope(self, client: TestClient) -> None:
        response = client.post("/assets", json={})

        assert response.status_code == 422
        body = response.json()
        assert body["error"]["code"] == "validation_error"
        assert "errors" in body["error"]["details"]
        assert len(body["error"]["details"]["errors"]) >= 1

    def test_custom_validator_failure_returns_standard_envelope(self, client: TestClient) -> None:
        """Blank identifier is rejected by a custom Pydantic validator
        (schemas/asset.py), not a plain type mismatch — this is the case
        that used to crash the validation handler itself (the raw
        ValueError inside Pydantic's error "ctx" isn't JSON-serializable
        without jsonable_encoder; see api/main.py's handler docstring)."""
        response = client.post("/assets", json={"identifier": "   "})

        assert response.status_code == 422
        body = response.json()
        assert body["error"]["code"] == "validation_error"

    def test_invalid_ip_returns_standard_envelope(self, client: TestClient) -> None:
        response = client.post(
            "/assets/hosts", json={"identifier": "web-envelope-01", "ip_address": "not-an-ip"}
        )

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"


class TestEveryErrorSharesOneShape:
    """A single structural assertion, run against every failure mode this
    milestone standardizes — proves there's exactly one shape, not that
    each individual field is correct (the classes above already do that)."""

    @pytest.mark.parametrize(
        "make_request",
        [
            lambda c: c.get(f"/assets/{uuid4()}"),
            lambda c: (
                c.post("/assets", json={"identifier": "shape-01"}),
                c.post("/assets", json={"identifier": "shape-01"}),
            )[-1],
            lambda c: c.post("/assets", json={}),
        ],
        ids=["not_found", "conflict", "validation"],
    )
    def test_response_has_exactly_the_error_envelope_shape(
        self, client: TestClient, make_request: Callable[[TestClient], Response]
    ) -> None:
        response = make_request(client)
        body = response.json()

        assert set(body.keys()) == {"error"}
        assert set(body["error"].keys()) == {"code", "message", "details"}
        assert isinstance(body["error"]["code"], str)
        assert isinstance(body["error"]["message"], str)
        assert isinstance(body["error"]["details"], dict)
