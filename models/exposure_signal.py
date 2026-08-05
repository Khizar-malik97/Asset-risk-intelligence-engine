"""The ExposureSignal domain model.

An ExposureSignal is a discrete, attributable fact about how an asset is
exposed to risk — e.g. "this host is internet-facing" or "this host has an
unpatched critical CVE." Multiple signals can attach to a single asset, and
each is independently timestamped and sourced, so the Risk Engine (Milestone
12) can explain a score down to the individual signal that caused it.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4


class ExposureSignalType(StrEnum):
    """The kind of exposure a signal represents."""

    INTERNET_FACING = "internet_facing"
    UNPATCHED_VULNERABILITY = "unpatched_vulnerability"
    OPEN_ADMIN_PORT = "open_admin_port"
    WEAK_AUTHENTICATION = "weak_authentication"
    END_OF_LIFE_SOFTWARE = "end_of_life_software"


class ExposureSeverity(StrEnum):
    """How severe this particular signal is, independent of asset criticality."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ExposureSignal:
    """A single, attributable exposure fact attached to an asset.

    Attributes:
        asset_id: The asset this signal is attached to.
        signal_type: What kind of exposure this is.
        severity: How severe this specific signal is.
        description: Free-text human-readable detail (e.g. "CVE-2024-12345").
        observed_at: When this exposure was recorded/confirmed.
        id: Unique identifier for this signal record.
    """

    asset_id: UUID
    signal_type: ExposureSignalType
    severity: ExposureSeverity
    description: str
    id: UUID = field(default_factory=uuid4)
    observed_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not self.description or not self.description.strip():
            raise ValueError("ExposureSignal description must not be empty.")
