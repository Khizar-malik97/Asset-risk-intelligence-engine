"""The Host domain model — a specialization of Asset."""

from dataclasses import dataclass

from models.asset import Asset
from models.enums import AssetType


@dataclass
class Host(Asset):
    """A host asset: a server, workstation, or other networked machine.

    Attributes:
        ip_address: The host's current or last-known IP address, if known.
        operating_system: Free-text OS description (e.g. "Windows Server 2022").
        is_internet_facing: Whether this host is reachable from the public internet.
            This is a raw fact about the host, distinct from an ExposureSignal
            (Milestone 10), which is a richer, attributable exposure record.
    """

    ip_address: str | None = None
    operating_system: str | None = None
    is_internet_facing: bool = False

    def __post_init__(self) -> None:
        super().__post_init__()
        self.asset_type = AssetType.HOST
