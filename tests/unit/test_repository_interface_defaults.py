"""Unit tests for AssetRepositoryInterface's default, naive search()
implementation (repositories/interfaces.py).

This default is deliberately NOT abstract — see its docstring — so any
repository that doesn't override it (the shared
tests/fakes/fake_asset_repository.py::FakeAssetRepository, used across
several other test files) still gets a correct, if unoptimized, search().
Every branch of that default gets its own direct test here rather than
being incidentally exercised (or not) by whichever other test happens to
construct a FakeAssetRepository — closing a real Milestone 22 coverage
gap: the asset_type branch specifically had no test anywhere before this.
"""

from models.asset import Asset
from models.enums import AssetCategory, AssetType
from models.host import Host
from models.user import User
from tests.fakes.fake_asset_repository import FakeAssetRepository


class TestDefaultSearch:
    def test_filters_by_category(self) -> None:
        repo = FakeAssetRepository()
        repo.add(Asset(identifier="server-01", category=AssetCategory.SERVER))
        repo.add(Asset(identifier="ws-01", category=AssetCategory.WORKSTATION))

        results = repo.search(category=AssetCategory.SERVER)

        assert [a.identifier for a in results] == ["server-01"]

    def test_filters_by_criticality(self) -> None:
        repo = FakeAssetRepository()
        repo.add(Asset(identifier="crit-01", is_critical=True))
        repo.add(Asset(identifier="normal-01", is_critical=False))

        results = repo.search(is_critical=True)

        assert [a.identifier for a in results] == ["crit-01"]

    def test_filters_by_asset_type(self) -> None:
        """The gap this file exists to close — no other test in the
        suite calls the interface's default search() with asset_type."""
        repo = FakeAssetRepository()
        repo.add(Host(identifier="host-01"))
        repo.add(User(identifier="user-01"))

        results = repo.search(asset_type=AssetType.HOST)

        assert [a.identifier for a in results] == ["host-01"]

    def test_filters_by_text_case_insensitively(self) -> None:
        repo = FakeAssetRepository()
        repo.add(Asset(identifier="WEB-prod-01"))
        repo.add(Asset(identifier="db-01"))

        results = repo.search(text="prod")

        assert [a.identifier for a in results] == ["WEB-prod-01"]

    def test_combined_filters_use_and_semantics(self) -> None:
        repo = FakeAssetRepository()
        repo.add(Host(identifier="match", category=AssetCategory.SERVER, is_critical=True))
        repo.add(
            Host(identifier="wrong-category", category=AssetCategory.WORKSTATION, is_critical=True)
        )
        repo.add(Host(identifier="wrong-criticality", category=AssetCategory.SERVER))

        results = repo.search(
            category=AssetCategory.SERVER, is_critical=True, asset_type=AssetType.HOST
        )

        assert [a.identifier for a in results] == ["match"]

    def test_no_filters_returns_everything(self) -> None:
        repo = FakeAssetRepository()
        repo.add(Asset(identifier="a"))
        repo.add(Asset(identifier="b"))

        results = repo.search()

        assert {a.identifier for a in results} == {"a", "b"}
