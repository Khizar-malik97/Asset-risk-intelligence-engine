"""The User domain model — a specialization of Asset."""

from dataclasses import dataclass

from models.asset import Asset
from models.enums import AssetType


@dataclass
class User(Asset):
    """A user account asset.

    Attributes:
        is_privileged: Whether this account has elevated/administrative
            privileges. A direct input to the Risk Engine (Milestone 12).
        department: Free-text organizational department, if known.
    """

    is_privileged: bool = False
    department: str | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        self.asset_type = AssetType.USER
