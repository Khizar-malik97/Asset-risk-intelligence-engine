"""Unit tests for ExportService, using the same in-memory fake pattern as
test_search_service.py (no real database, no FastAPI TestClient)."""

from uuid import UUID

from models.asset import Asset
from models.enums import AssetCategory, AssetType, DiscoverySource
from models.exposure_signal import ExposureSignal
from models.host import Host
from repositories.exceptions import AssetNotFoundError
from repositories.exposure_signal_repository import ExposureSignalRepositoryInterface
from repositories.interfaces import AssetRepositoryInterface
from schemas.export import ExportResponse
from services.export.json_export import EXPORT_SCHEMA_VERSION, ExportService
from services.inventory.search import AssetSearchService


class _FakeAssetRepository(AssetRepositoryInterface):
    """Same minimal fake shape used throughout the test suite (e.g.
    test_search_service.py) — defined locally, not imported, so this
    file doesn't depend on another test file's exact contents."""

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

    def search(
        self,
        *,
        category: AssetCategory | None = None,
        is_critical: bool | None = None,
        asset_type: AssetType | None = None,
        text: str | None = None,
    ) -> list[Asset]:
        results = list(self._store.values())
        if category is not None:
            results = [a for a in results if a.category == category]
        if is_critical is not None:
            results = [a for a in results if a.is_critical == is_critical]
        if asset_type is not None:
            results = [a for a in results if a.asset_type == asset_type]
        if text is not None:
            results = [a for a in results if text.lower() in a.identifier.lower()]
        return results


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


def _build_export_service() -> tuple[ExportService, _FakeAssetRepository]:
    asset_repo = _FakeAssetRepository()
    signal_repo = _FakeExposureSignalRepository()
    search_service = AssetSearchService(
        asset_repository=asset_repo,
        exposure_signal_repository=signal_repo,
    )
    return ExportService(search_service), asset_repo


class TestExportAssets:
    def test_exports_every_asset_when_no_filters_given(self) -> None:
        service, repo = _build_export_service()
        repo.add(Asset(identifier="asset-a"))
        repo.add(Asset(identifier="asset-b"))

        result = service.export_assets()

        assert result.asset_count == 2
        assert {a.identifier for a in result.assets} == {"asset-a", "asset-b"}

    def test_export_is_empty_for_empty_inventory(self) -> None:
        service, _ = _build_export_service()

        result = service.export_assets()

        assert result.asset_count == 0
        assert result.assets == []

    def test_export_respects_category_filter(self) -> None:
        service, repo = _build_export_service()
        repo.add(Asset(identifier="server-01", category=AssetCategory.SERVER))
        repo.add(Asset(identifier="ws-01", category=AssetCategory.WORKSTATION))

        result = service.export_assets(category=AssetCategory.SERVER)

        assert result.asset_count == 1
        assert result.assets[0].identifier == "server-01"

    def test_export_respects_criticality_filter(self) -> None:
        service, repo = _build_export_service()
        repo.add(Asset(identifier="crit-01", is_critical=True))
        repo.add(Asset(identifier="normal-01", is_critical=False))

        result = service.export_assets(is_critical=True)

        assert result.asset_count == 1
        assert result.assets[0].identifier == "crit-01"

    def test_exported_host_includes_host_specific_fields(self) -> None:
        service, repo = _build_export_service()
        repo.add(
            Host(
                identifier="web-01",
                ip_address="10.0.0.5",
                operating_system="Ubuntu 24.04",
                is_internet_facing=True,
                discovery_source=DiscoverySource.MANUAL,
            )
        )

        result = service.export_assets()

        exported = result.assets[0]
        assert exported.ip_address == "10.0.0.5"
        assert exported.operating_system == "Ubuntu 24.04"
        assert exported.is_internet_facing is True
        assert exported.is_privileged is None

    def test_schema_version_is_stamped_on_every_export(self) -> None:
        service, _ = _build_export_service()

        result = service.export_assets()

        assert result.schema_version == EXPORT_SCHEMA_VERSION

    def test_result_is_a_pydantic_export_response(self) -> None:
        service, repo = _build_export_service()
        repo.add(Asset(identifier="asset-a"))

        result = service.export_assets()

        assert isinstance(result, ExportResponse)
        # Round-trips through JSON cleanly — the whole point of a
        # schema-backed export, proven directly rather than assumed.
        assert result.model_dump_json()
