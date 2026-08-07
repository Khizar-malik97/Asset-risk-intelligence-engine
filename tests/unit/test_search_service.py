"""Unit tests for AssetSearchService, using in-memory fakes for both
repositories so these tests run with no real database at all."""

from uuid import UUID

import pytest

from models.asset import Asset
from models.enums import AssetCategory, AssetType, DiscoverySource, RiskLevel
from models.exposure_signal import ExposureSeverity, ExposureSignal, ExposureSignalType
from models.host import Host
from repositories.exceptions import AssetNotFoundError
from repositories.exposure_signal_repository import ExposureSignalRepositoryInterface
from repositories.interfaces import AssetRepositoryInterface
from services.inventory.search import AssetSearchService
from services.risk_engine.base import RiskFactor, RiskFactorResult
from services.risk_engine.scoring import RiskScoringEngine
from utils.exceptions import InvalidRequestError


class _FakeAssetRepository(AssetRepositoryInterface):
    """Minimal in-test fake — same shape as tests/fakes/FakeAssetRepository,
    defined locally so this test file doesn't depend on that file's exact
    contents changing in future milestones."""

    def __init__(self) -> None:
        self._store: dict[UUID, Asset] = {}

    def add(self, asset: Asset) -> Asset:
        self._store[asset.id] = asset
        return asset

    def get_by_id(self, asset_id: UUID) -> Asset | None:
        return self._store.get(asset_id)

    def get_by_identifier(self, identifier: str) -> Asset | None:
        for asset in self._store.values():
            if asset.identifier == identifier:
                return asset
        return None

    def list_all(self) -> list[Asset]:
        return list(self._store.values())

    def list_critical(self) -> list[Asset]:
        return [a for a in self._store.values() if a.is_critical]

    def list_by_category(self, category: AssetCategory) -> list[Asset]:
        return [a for a in self._store.values() if a.category == category]

    def list_hosts(self) -> list[Asset]:
        return [a for a in self._store.values() if isinstance(a, Host)]

    def list_users(self) -> list[Asset]:
        return [a for a in self._store.values() if a.asset_type == AssetType.USER]

    def update(self, asset: Asset) -> Asset:
        if asset.id not in self._store:
            raise AssetNotFoundError(asset.id)
        self._store[asset.id] = asset
        return asset

    def delete(self, asset_id: UUID) -> None:
        if asset_id not in self._store:
            raise AssetNotFoundError(asset_id)
        del self._store[asset_id]


class _FakeExposureSignalRepository(ExposureSignalRepositoryInterface):
    """Minimal in-test fake for ExposureSignalRepositoryInterface."""

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


class _AlwaysTriggerFactor(RiskFactor):
    name = "always_trigger"
    description = "Triggers for every asset, for test purposes."

    def evaluate(self, asset: Asset, exposure_signals: list[ExposureSignal]) -> RiskFactorResult:
        return RiskFactorResult(
            factor_name=self.name, weight_applied=self.weight, triggered=True, reason="test"
        )


class _NeverTriggerFactor(RiskFactor):
    name = "never_trigger"
    description = "Never triggers, for test purposes."

    def evaluate(self, asset: Asset, exposure_signals: list[ExposureSignal]) -> RiskFactorResult:
        return RiskFactorResult(
            factor_name=self.name, weight_applied=0, triggered=False, reason="test"
        )


def _make_host(
    identifier: str,
    category: AssetCategory = AssetCategory.SERVER,
    is_critical: bool = False,
) -> Host:
    return Host(
        identifier=identifier,
        category=category,
        is_critical=is_critical,
        discovery_source=DiscoverySource.MANUAL,
    )


@pytest.fixture
def asset_repo() -> _FakeAssetRepository:
    return _FakeAssetRepository()


@pytest.fixture
def signal_repo() -> _FakeExposureSignalRepository:
    return _FakeExposureSignalRepository()


class TestBasicFilters:
    def test_filter_by_category(self, asset_repo, signal_repo):
        asset_repo.add(_make_host("web-01", category=AssetCategory.SERVER))
        asset_repo.add(_make_host("ws-01", category=AssetCategory.WORKSTATION))
        service = AssetSearchService(asset_repo, signal_repo)

        results = service.search(category=AssetCategory.SERVER)

        assert [a.identifier for a in results] == ["web-01"]

    def test_filter_by_criticality(self, asset_repo, signal_repo):
        asset_repo.add(_make_host("web-01", is_critical=True))
        asset_repo.add(_make_host("web-02", is_critical=False))
        service = AssetSearchService(asset_repo, signal_repo)

        results = service.search(is_critical=True)

        assert [a.identifier for a in results] == ["web-01"]

    def test_combined_category_and_criticality(self, asset_repo, signal_repo):
        asset_repo.add(_make_host("web-01", category=AssetCategory.SERVER, is_critical=True))
        asset_repo.add(_make_host("web-02", category=AssetCategory.SERVER, is_critical=False))
        asset_repo.add(_make_host("ws-01", category=AssetCategory.WORKSTATION, is_critical=True))
        service = AssetSearchService(asset_repo, signal_repo)

        results = service.search(category=AssetCategory.SERVER, is_critical=True)

        assert [a.identifier for a in results] == ["web-01"]

    def test_no_filters_returns_everything(self, asset_repo, signal_repo):
        asset_repo.add(_make_host("web-01"))
        asset_repo.add(_make_host("web-02"))
        service = AssetSearchService(asset_repo, signal_repo)

        results = service.search()

        assert len(results) == 2

    def test_no_matches_returns_empty_list(self, asset_repo, signal_repo):
        asset_repo.add(_make_host("web-01", category=AssetCategory.SERVER))
        service = AssetSearchService(asset_repo, signal_repo)

        results = service.search(category=AssetCategory.DATABASE_SERVER)

        assert results == []


class TestExposureSignalFilter:
    def test_filters_to_assets_with_matching_signal(self, asset_repo, signal_repo):
        host_with_signal = _make_host("web-01")
        host_without_signal = _make_host("web-02")
        asset_repo.add(host_with_signal)
        asset_repo.add(host_without_signal)
        signal_repo.add(
            ExposureSignal(
                asset_id=host_with_signal.id,
                signal_type=ExposureSignalType.INTERNET_FACING,
                severity=ExposureSeverity.HIGH,
                description="test",
            )
        )
        service = AssetSearchService(asset_repo, signal_repo)

        results = service.search(exposure_signal_type=ExposureSignalType.INTERNET_FACING)

        assert [a.identifier for a in results] == ["web-01"]

    def test_no_signals_at_all_returns_empty(self, asset_repo, signal_repo):
        asset_repo.add(_make_host("web-01"))
        service = AssetSearchService(asset_repo, signal_repo)

        results = service.search(exposure_signal_type=ExposureSignalType.INTERNET_FACING)

        assert results == []

    def test_combined_with_category_filter(self, asset_repo, signal_repo):
        server_with_signal = _make_host("web-01", category=AssetCategory.SERVER)
        workstation_with_signal = _make_host("ws-01", category=AssetCategory.WORKSTATION)
        asset_repo.add(server_with_signal)
        asset_repo.add(workstation_with_signal)
        for asset in (server_with_signal, workstation_with_signal):
            signal_repo.add(
                ExposureSignal(
                    asset_id=asset.id,
                    signal_type=ExposureSignalType.INTERNET_FACING,
                    severity=ExposureSeverity.HIGH,
                    description="test",
                )
            )
        service = AssetSearchService(asset_repo, signal_repo)

        results = service.search(
            category=AssetCategory.SERVER,
            exposure_signal_type=ExposureSignalType.INTERNET_FACING,
        )

        assert [a.identifier for a in results] == ["web-01"]


class TestRiskLevelFilter:
    def test_raises_without_configured_engine(self, asset_repo, signal_repo):
        service = AssetSearchService(asset_repo, signal_repo)  # no engine

        with pytest.raises(InvalidRequestError):
            service.search(risk_level=RiskLevel.HIGH)

    def test_filters_by_computed_risk_level(self, asset_repo, signal_repo):
        high_risk_host = _make_host("web-01")
        low_risk_host = _make_host("web-02")
        asset_repo.add(high_risk_host)
        asset_repo.add(low_risk_host)

        engine = RiskScoringEngine(
            factors=[_AlwaysTriggerFactor(weight=100)],
            thresholds={
                RiskLevel.LOW: 0,
                RiskLevel.MEDIUM: 25,
                RiskLevel.HIGH: 50,
                RiskLevel.CRITICAL: 75,
            },
        )
        # Both hosts score identically here since _AlwaysTriggerFactor
        # ignores asset state — this test proves the wiring works; a
        # richer scenario (differing scores) is covered by the
        # integration test using the real scoring engine + real factors.
        service = AssetSearchService(asset_repo, signal_repo, risk_scoring_engine=engine)

        results = service.search(risk_level=RiskLevel.CRITICAL)

        assert {a.identifier for a in results} == {"web-01", "web-02"}

    def test_filters_out_non_matching_risk_level(self, asset_repo, signal_repo):
        host = _make_host("web-01")
        asset_repo.add(host)

        engine = RiskScoringEngine(
            factors=[_NeverTriggerFactor(weight=100)],
            thresholds={
                RiskLevel.LOW: 0,
                RiskLevel.MEDIUM: 25,
                RiskLevel.HIGH: 50,
                RiskLevel.CRITICAL: 75,
            },
        )
        service = AssetSearchService(asset_repo, signal_repo, risk_scoring_engine=engine)

        results = service.search(risk_level=RiskLevel.CRITICAL)

        assert results == []
