"""Discovery Reconciliation Service.

Merges duplicate asset records that share an identifier — the expected
byproduct of Discovery (Milestone 15) deliberately allowing duplicates — 
into one canonical record per real-world asset.

Matching strategy: exact identifier match (same granularity as
AssetRepositoryInterface.get_by_identifier()). Fuzzier matching (hostname
normalization, IP-based correlation) is explicitly out of scope here —
flag if a real need for it shows up, so it can be scoped properly rather
than guessed at.

Merge rule: the most-recently-seen candidate becomes canonical, taken as a
whole record (its fields are internally consistent — all recorded
together) — with exactly two deliberate overrides:
  - is_critical: TRUE if ANY duplicate was flagged critical. A criticality
    flag must never be silently lost because a newer, less-informed
    discovery pass didn't know about it.
  - first_seen: the EARLIEST first_seen across all duplicates, so an
    asset's tracked age reflects when it was truly first observed, not
    just when the winning record happened to be created.

All non-canonical duplicates are deleted after the canonical record is
updated.
"""

from collections import defaultdict
from dataclasses import dataclass

from logging_.logger import get_logger
from models.asset import Asset
from repositories.interfaces import AssetRepositoryInterface

logger = get_logger(__name__)


@dataclass(frozen=True)
class ReconciliationGroupResult:
    """Outcome of reconciling one identifier's duplicate group.

    Attributes:
        identifier: The shared identifier that was reconciled.
        canonical_asset: The surviving, merged record.
        duplicates_removed: How many other records were deleted.
    """

    identifier: str
    canonical_asset: Asset
    duplicates_removed: int


@dataclass(frozen=True)
class ReconciliationRunResult:
    """Summary of one reconcile_all() call.

    Attributes:
        groups_reconciled: One entry per identifier that had duplicates
            (identifiers with only one record are not included — nothing
            to reconcile).
        total_duplicates_removed: Sum of duplicates_removed across every group.
    """

    groups_reconciled: list[ReconciliationGroupResult]
    total_duplicates_removed: int


class ReconciliationService:
    """Finds and merges duplicate asset records sharing an identifier."""

    def __init__(self, repository: AssetRepositoryInterface) -> None:
        self._repository = repository

    def reconcile_all(self) -> ReconciliationRunResult:
        """Scan the entire inventory, merge every group of duplicates, and
        persist the result.

        Identifiers with only one record are left untouched — this method
        is idempotent: running it twice in a row with no new duplicates
        does nothing on the second run.
        """
        groups: dict[str, list[Asset]] = defaultdict(list)
        for asset in self._repository.list_all():
            groups[asset.identifier].append(asset)

        group_results: list[ReconciliationGroupResult] = []
        total_removed = 0

        for identifier, candidates in groups.items():
            if len(candidates) < 2:
                continue

            canonical, duplicates = self._merge_group(candidates)
            updated_canonical = self._repository.update(canonical)
            for duplicate in duplicates:
                self._repository.delete(duplicate.id)

            logger.info(
                "Reconciled duplicate assets",
                extra={
                    "identifier": identifier,
                    "canonical_asset_id": str(updated_canonical.id),
                    "duplicates_removed": len(duplicates),
                },
            )

            group_results.append(
                ReconciliationGroupResult(
                    identifier=identifier,
                    canonical_asset=updated_canonical,
                    duplicates_removed=len(duplicates),
                )
            )
            total_removed += len(duplicates)

        return ReconciliationRunResult(
            groups_reconciled=group_results, total_duplicates_removed=total_removed
        )

    @staticmethod
    def _merge_group(candidates: list[Asset]) -> tuple[Asset, list[Asset]]:
        """Pick the canonical record and apply the two business-rule
        overrides. `candidates` may mix asset types (e.g. a Host and a
        plain Asset sharing an identifier) — both overrides operate on
        base Asset fields, so this works uniformly regardless of type.
        """
        # Sort by last_seen descending; tie-break on id for determinism
        # (no semantic meaning, just a stable, reproducible choice).
        ordered = sorted(candidates, key=lambda a: (a.last_seen, str(a.id)), reverse=True)
        canonical, duplicates = ordered[0], ordered[1:]

        canonical.is_critical = any(candidate.is_critical for candidate in candidates)
        canonical.first_seen = min(candidate.first_seen for candidate in candidates)

        return canonical, duplicates
