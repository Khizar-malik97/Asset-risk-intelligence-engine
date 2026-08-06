"""Unit tests for services/discovery/discovery_service.py and
services/discovery/providers/static_provider.py."""

from models.asset import Asset
from models.enums import DiscoverySource
from models.host import Host
from services.discovery.discovery_service import DiscoveryService
from services.discovery.providers.static_provider import StaticDiscoveryProvider
from tests.fakes.fake_asset_repository import FakeAssetRepository


class TestStaticDiscoveryProvider:
    def test_discover_returns_configured_assets(self) -> None:
        assets = [Asset(identifier="a1"), Asset(identifier="a2")]
        provider = StaticDiscoveryProvider(name="test-feed", assets=assets)

        result = provider.discover()

        assert len(result) == 2
        assert {a.identifier for a in result} == {"a1", "a2"}

    def test_discover_returns_empty_list_when_configured_empty(self) -> None:
        provider = StaticDiscoveryProvider(name="empty-feed", assets=[])

        assert provider.discover() == []

    def test_discover_returns_a_fresh_list_each_call(self) -> None:
        """Callers mutating the returned list must not affect the
        provider's internal state on subsequent calls."""
        assets = [Asset(identifier="a1")]
        provider = StaticDiscoveryProvider(name="test-feed", assets=assets)

        first_call = provider.discover()
        first_call.append(Asset(identifier="injected"))

        second_call = provider.discover()
        assert len(second_call) == 1


class TestDiscoveryService:
    def test_run_discovery_persists_all_discovered_assets(self) -> None:
        provider = StaticDiscoveryProvider(
            name="feed-1", assets=[Asset(identifier="a1"), Asset(identifier="a2")]
        )
        repository = FakeAssetRepository()
        service = DiscoveryService(providers=[provider], repository=repository)

        result = service.run_discovery()

        assert len(result.assets) == 2
        assert len(repository.list_all()) == 2

    def test_run_discovery_forces_discovery_source(self) -> None:
        """Even if a provider set discovery_source=MANUAL, DiscoveryService
        must override it — this is a structural guarantee, not a
        convention providers are trusted to follow."""
        mislabeled = Asset(identifier="mislabeled", discovery_source=DiscoverySource.MANUAL)
        provider = StaticDiscoveryProvider(name="feed-1", assets=[mislabeled])
        repository = FakeAssetRepository()
        service = DiscoveryService(providers=[provider], repository=repository)

        result = service.run_discovery()

        assert result.assets[0].discovery_source == DiscoverySource.DISCOVERY_PROVIDER

    def test_run_discovery_across_multiple_providers(self) -> None:
        provider_a = StaticDiscoveryProvider(name="feed-a", assets=[Asset(identifier="a1")])
        provider_b = StaticDiscoveryProvider(
            name="feed-b", assets=[Host(identifier="h1"), Host(identifier="h2")]
        )
        repository = FakeAssetRepository()
        service = DiscoveryService(providers=[provider_a, provider_b], repository=repository)

        result = service.run_discovery()

        assert len(result.assets) == 3
        assert result.assets_by_provider == {"feed-a": 1, "feed-b": 2}

    def test_run_discovery_with_no_providers_does_nothing(self) -> None:
        repository = FakeAssetRepository()
        service = DiscoveryService(providers=[], repository=repository)

        result = service.run_discovery()

        assert result.assets == []
        assert result.assets_by_provider == {}

    def test_run_discovery_allows_duplicate_identifiers(self) -> None:
        """Unlike AssetInventoryService.register_asset(), Discovery must
        NOT reject duplicate identifiers — reconciling them is Milestone
        16's job, not Discovery's."""
        provider_a = StaticDiscoveryProvider(name="feed-a", assets=[Asset(identifier="dup-host")])
        provider_b = StaticDiscoveryProvider(name="feed-b", assets=[Asset(identifier="dup-host")])
        repository = FakeAssetRepository()
        service = DiscoveryService(providers=[provider_a, provider_b], repository=repository)

        result = service.run_discovery()

        assert len(result.assets) == 2
        matches = [a for a in repository.list_all() if a.identifier == "dup-host"]
        assert len(matches) == 2

    def test_empty_provider_result_recorded_in_counts(self) -> None:
        provider = StaticDiscoveryProvider(name="quiet-feed", assets=[])
        repository = FakeAssetRepository()
        service = DiscoveryService(providers=[provider], repository=repository)

        result = service.run_discovery()

        assert result.assets_by_provider == {"quiet-feed": 0}
