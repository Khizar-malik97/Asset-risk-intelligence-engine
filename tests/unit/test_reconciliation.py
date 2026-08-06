"""Unit tests for services/discovery/reconciliation.py."""

from datetime import UTC, datetime, timedelta

from models.asset import Asset
from models.host import Host
from services.discovery.reconciliation import ReconciliationService
from tests.fakes.fake_asset_repository import FakeAssetRepository


def _asset(identifier: str, days_ago: int, is_critical: bool = False) -> Asset:
    asset = Asset(identifier=identifier, is_critical=is_critical)
    asset.last_seen = datetime.now(UTC) - timedelta(days=days_ago)
    asset.first_seen = datetime.now(UTC) - timedelta(days=days_ago)
    return asset


class TestNoDuplicates:
    def test_unique_identifiers_are_untouched(self) -> None:
        repository = FakeAssetRepository()
        repository.add(_asset("host-1", days_ago=1))
        repository.add(_asset("host-2", days_ago=2))
        service = ReconciliationService(repository)

        result = service.reconcile_all()

        assert result.groups_reconciled == []
        assert result.total_duplicates_removed == 0
        assert len(repository.list_all()) == 2

    def test_empty_inventory(self) -> None:
        repository = FakeAssetRepository()
        service = ReconciliationService(repository)

        result = service.reconcile_all()

        assert result.groups_reconciled == []
        assert result.total_duplicates_removed == 0


class TestBasicMerge:
    def test_most_recently_seen_becomes_canonical(self) -> None:
        repository = FakeAssetRepository()
        older = repository.add(_asset("dup-host", days_ago=10))
        newer = repository.add(_asset("dup-host", days_ago=1))
        service = ReconciliationService(repository)

        result = service.reconcile_all()

        assert len(result.groups_reconciled) == 1
        group = result.groups_reconciled[0]
        assert group.canonical_asset.id == newer.id
        assert group.duplicates_removed == 1

        remaining = repository.list_all()
        assert len(remaining) == 1
        assert remaining[0].id == newer.id
        assert repository.get_by_id(older.id) is None

    def test_three_way_duplicate_leaves_one_record(self) -> None:
        repository = FakeAssetRepository()
        repository.add(_asset("triple-host", days_ago=10))
        repository.add(_asset("triple-host", days_ago=5))
        newest = repository.add(_asset("triple-host", days_ago=1))
        service = ReconciliationService(repository)

        result = service.reconcile_all()

        assert result.groups_reconciled[0].duplicates_removed == 2
        remaining = repository.list_all()
        assert len(remaining) == 1
        assert remaining[0].id == newest.id

    def test_multiple_independent_groups_reconciled_separately(self) -> None:
        repository = FakeAssetRepository()
        repository.add(_asset("group-a", days_ago=10))
        repository.add(_asset("group-a", days_ago=1))
        repository.add(_asset("group-b", days_ago=5))
        repository.add(_asset("group-b", days_ago=2))
        repository.add(_asset("unique", days_ago=1))
        service = ReconciliationService(repository)

        result = service.reconcile_all()

        assert len(result.groups_reconciled) == 2
        assert result.total_duplicates_removed == 2
        assert len(repository.list_all()) == 3  # 1 per group + the unique one


class TestCriticalFlagOverride:
    def test_older_critical_flag_is_preserved_on_canonical(self) -> None:
        """The core safety rule: a critical flag must survive even if the
        winning (most-recent) record didn't carry it."""
        repository = FakeAssetRepository()
        repository.add(_asset("crit-host", days_ago=10, is_critical=True))
        repository.add(_asset("crit-host", days_ago=1, is_critical=False))
        service = ReconciliationService(repository)

        result = service.reconcile_all()

        assert result.groups_reconciled[0].canonical_asset.is_critical is True

    def test_neither_critical_stays_non_critical(self) -> None:
        repository = FakeAssetRepository()
        repository.add(_asset("normal-host", days_ago=10, is_critical=False))
        repository.add(_asset("normal-host", days_ago=1, is_critical=False))
        service = ReconciliationService(repository)

        result = service.reconcile_all()

        assert result.groups_reconciled[0].canonical_asset.is_critical is False

    def test_newer_critical_flag_also_preserved(self) -> None:
        repository = FakeAssetRepository()
        repository.add(_asset("crit-host-2", days_ago=10, is_critical=False))
        repository.add(_asset("crit-host-2", days_ago=1, is_critical=True))
        service = ReconciliationService(repository)

        result = service.reconcile_all()

        assert result.groups_reconciled[0].canonical_asset.is_critical is True


class TestFirstSeenOverride:
    def test_canonical_first_seen_becomes_the_earliest(self) -> None:
        repository = FakeAssetRepository()
        repository.add(_asset("aged-host", days_ago=100))  # earliest first_seen
        repository.add(_asset("aged-host", days_ago=1))  # most recent (wins canonical)
        service = ReconciliationService(repository)

        result = service.reconcile_all()

        canonical = result.groups_reconciled[0].canonical_asset
        # canonical's own first_seen (1 day ago) should be overridden by
        # the older duplicate's first_seen (100 days ago)
        age_days = (datetime.now(UTC) - canonical.first_seen).days
        assert age_days >= 100


class TestMixedTypes:
    def test_host_and_generic_asset_sharing_identifier_still_merge(self) -> None:
        """Both overrides operate on base Asset fields, so mismatched
        types merge without error — canonical is whichever is most recent,
        regardless of type."""
        repository = FakeAssetRepository()
        generic = Asset(identifier="mixed-type", is_critical=True)
        generic.last_seen = datetime.now(UTC) - timedelta(days=10)
        generic.first_seen = datetime.now(UTC) - timedelta(days=10)
        repository.add(generic)

        host = Host(identifier="mixed-type", ip_address="10.0.0.9")
        host.last_seen = datetime.now(UTC) - timedelta(days=1)
        host.first_seen = datetime.now(UTC) - timedelta(days=1)
        repository.add(host)

        service = ReconciliationService(repository)

        result = service.reconcile_all()

        canonical = result.groups_reconciled[0].canonical_asset
        assert isinstance(canonical, Host)  # most-recent (the Host) wins wholesale
        assert canonical.is_critical is True  # critical flag still carried over


class TestIdempotency:
    def test_running_twice_in_a_row_is_a_no_op_the_second_time(self) -> None:
        repository = FakeAssetRepository()
        repository.add(_asset("dup-host", days_ago=10))
        repository.add(_asset("dup-host", days_ago=1))
        service = ReconciliationService(repository)

        first_result = service.reconcile_all()
        second_result = service.reconcile_all()

        assert first_result.total_duplicates_removed == 1
        assert second_result.total_duplicates_removed == 0
        assert second_result.groups_reconciled == []
