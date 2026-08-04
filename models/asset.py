"""The base Asset domain model.

`Asset` represents anything the platform tracks: a host, a user, or (in the
future) something else entirely. `Host` and `User` (see host.py, user.py)
extend this with type-specific fields.

This is a domain model, not a database model and not an API schema — see
docs/architecture.md ADR-005 for why those stay separate.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from models.enums import AssetCategory, AssetType, DiscoverySource


@dataclass
class Asset:
    """A tracked asset: its identity, classification, and lifecycle metadata.

    Attributes:
        id: Unique identifier, generated automatically if not provided.
        identifier: The human-meaningful name for this asset (e.g. a hostname
            or username). Not guaranteed unique at this layer — deduplication
            is the Discovery Reconciliation engine's job (Milestone 16).
        asset_type: What kind of asset this is (generic/host/user).
        category: Business classification (server, workstation, etc).
        is_critical: Whether this asset has been flagged as business-critical.
        discovery_source: How this asset entered the inventory.
        first_seen: When this asset was first recorded.
        last_seen: When this asset was last confirmed to still exist/be active.
    """

    identifier: str
    asset_type: AssetType = AssetType.GENERIC
    category: AssetCategory = AssetCategory.UNCATEGORIZED
    is_critical: bool = False
    discovery_source: DiscoverySource = DiscoverySource.MANUAL
    id: UUID = field(default_factory=uuid4)
    first_seen: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_seen: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not self.identifier or not self.identifier.strip():
            raise ValueError("Asset identifier must not be empty.")

    def is_stale(self, staleness_threshold_days: int = 30) -> bool:
        """Return True if this asset hasn't been seen within the threshold.

        Args:
            staleness_threshold_days: Number of days of inactivity before an
                asset is considered stale. Defaults to 30.
        """
        age = datetime.now(UTC) - self.last_seen
        return age.days >= staleness_threshold_days

    def age_in_days(self) -> int:
        """Return how many days ago this asset was first seen."""
        return (datetime.now(UTC) - self.first_seen).days

    def mark_seen(self) -> None:
        """Update last_seen to now. Called whenever a new signal confirms
        this asset is still active (used by the Discovery engine, Milestone 11)."""
        self.last_seen = datetime.now(UTC)
