"""Unit tests for IntegrationContextService — real AssetInventoryService/
ExposureSignalService/RiskScoringEngine/ConfidenceScoringEngine wired
together against the shared in-memory fakes (no real database), same
"real config, fake persistence" pattern test_risk_scoring.py's golden-value
tests already use.
"""

from uuid import UUID, uuid4

import pytest

from models.asset import Asset
from models.enums import AssetCategory
from models.exposure_signal import ExposureSignal
from repositories.exceptions import AssetNotFoundError
from repositories.exposure_signal_repository import ExposureSignalRepositoryInterface
from repositories.interfaces import AssetRepositoryInterface
from services.integration.context_service import IntegrationContextService
from services.inventory.exposure_signal_service import ExposureSignalService
from services.inventory.inventory_service import AssetInventoryService
from services.risk_engine.confidence import ConfidenceScoringEngine
from services.risk_engine.registry import get_registered_factors
from services.risk_engine.scoring import RiskScoringEngine
from services.risk_engine.thresholds import load_risk_thresholds
from services.risk_engine.weights import build_factors, load_risk_weights
from tests.fakes.fake_asset_repository import FakeAssetRepository

ServiceFixture = tuple[IntegrationContextService, FakeAssetRepository]


class _FakeExposureSignalRepository(ExposureSignalRepositoryInterface):
    def __init__(self) -> None:
        self._signals: dict[UUID, list[ExposureSignal]] = {}

    def add(self, signal: ExposureSignal) -> ExposureSignal:
        self._signals.setdefault(signal.asset_id, []).append(signal)
        return signal

    def list_for_asset(self, asset_id: UUID) -> list[ExposureSignal]:
        return self._signals.get(asset_id, [])

    def remove(self, signal_id: UUID) -> None:
        for signals in self._signals.values():
            signals[:] = [s for s in signals if s.id != signal_id]


@pytest.fixture()
def service() -> tuple[IntegrationContextService, FakeAssetRepository]:
    asset_repo: AssetRepositoryInterface = FakeAssetRepository()
    signal_repo = _FakeExposureSignalRepository()

    weights = load_risk_weights("config/risk_weights.yaml")
    thresholds = load_risk_thresholds("config/risk_thresholds.yaml")
    factors = build_factors(weights, registry=get_registered_factors())
    risk_engine = RiskScoringEngine(factors=factors, thresholds=thresholds)

    return (
        IntegrationContextService(
            inventory_service=AssetInventoryService(asset_repo),
            signal_service=ExposureSignalService(signal_repo),
            risk_engine=risk_engine,
            confidence_engine=ConfidenceScoringEngine(),
        ),
        asset_repo,  # type: ignore[return-value]
    )


class TestGetContext:
    def test_returns_none_for_missing_asset(self, service: ServiceFixture) -> None:
        integration_service, _ = service

        assert integration_service.get_context(uuid4()) is None

    def test_returns_context_reflecting_criticality(self, service: ServiceFixture) -> None:
        integration_service, repo = service
        asset = Asset(identifier="critical-01", is_critical=True)
        repo.add(asset)

        context = integration_service.get_context(asset.id)

        assert context is not None
        assert context.asset_id == asset.id
        assert context.is_critical is True
        assert context.risk_score == 30
        assert context.risk_level.value == "medium"


class TestBulkContext:
    def test_separates_found_from_not_found(self, service: ServiceFixture) -> None:
        integration_service, repo = service
        found_asset = Asset(identifier="bulk-01")
        repo.add(found_asset)
        missing_id = uuid4()

        result = integration_service.bulk_context([found_asset.id, missing_id])

        assert len(result.found) == 1
        assert result.found[0].asset_id == found_asset.id
        assert result.not_found == [missing_id]

    def test_empty_list_returns_empty_result(self, service: ServiceFixture) -> None:
        integration_service, _ = service

        result = integration_service.bulk_context([])

        assert result.found == []
        assert result.not_found == []


class TestSummarize:
    def test_empty_inventory(self, service: ServiceFixture) -> None:
        integration_service, _ = service

        summary = integration_service.summarize()

        assert summary.total_assets == 0
        assert summary.critical_assets == 0
        assert summary.by_category == []
        assert len(summary.by_risk_level) == 4
        assert all(row.count == 0 for row in summary.by_risk_level)

    def test_counts_reflect_real_data(self, service: ServiceFixture) -> None:
        integration_service, repo = service
        repo.add(Asset(identifier="s1", category=AssetCategory.SERVER))
        repo.add(Asset(identifier="s2", category=AssetCategory.SERVER))
        critical = Asset(identifier="c1", category=AssetCategory.WORKSTATION, is_critical=True)
        repo.add(critical)

        summary = integration_service.summarize()

        assert summary.total_assets == 3
        assert summary.critical_assets == 1
        by_category = {row.category.value: row.count for row in summary.by_category}
        assert by_category["server"] == 2
        assert by_category["workstation"] == 1
        by_risk = {row.risk_level.value: row.count for row in summary.by_risk_level}
        assert by_risk["medium"] == 1
        assert by_risk["low"] == 2


class TestAssetNotFoundIsNotRaisedHere:
    """IntegrationContextService itself never raises AssetNotFoundError —
    that's the router's job (404 mapping), same separation of concerns
    api/routers/assets.py already uses. This test documents that
    boundary explicitly rather than leaving it implicit."""

    def test_get_context_returns_none_not_raises(self, service: ServiceFixture) -> None:
        integration_service, _ = service

        try:
            result = integration_service.get_context(uuid4())
        except AssetNotFoundError:
            pytest.fail("IntegrationContextService.get_context() must return None, not raise")

        assert result is None
