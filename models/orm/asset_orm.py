"""ORM table definitions for Asset, Host, and User.

These mirror the domain models in models/asset.py, models/host.py, and
models/user.py — but are a SEPARATE set of classes. Domain models describe
business behavior (is_stale(), mark_seen()); ORM models describe how that
data is stored. Keeping them separate (see docs/architecture.md ADR-005)
means a change to how we persist data never forces a change to business
logic, and vice versa.

Uses SQLAlchemy joined-table inheritance: `assets` holds fields shared by
every asset type; `hosts` and `users` hold only their type-specific extra
columns, joined back to `assets` via a shared primary key.
"""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from models.enums import AssetCategory, AssetType, DiscoverySource
from models.orm.base import Base


class AssetORM(Base):
    """The `assets` table — shared columns for every asset, regardless of type."""

    __tablename__ = "assets"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    identifier: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    asset_type: Mapped[AssetType] = mapped_column(
        String(20), nullable=False, default=AssetType.GENERIC
    )
    category: Mapped[AssetCategory] = mapped_column(
        String(50), nullable=False, default=AssetCategory.UNCATEGORIZED, index=True
    )
    is_critical: Mapped[bool] = mapped_column(default=False, index=True)
    discovery_source: Mapped[DiscoverySource] = mapped_column(
        String(20), nullable=False, default=DiscoverySource.MANUAL
    )
    first_seen: Mapped[datetime] = mapped_column(nullable=False)
    last_seen: Mapped[datetime] = mapped_column(nullable=False, index=True)

    # Polymorphic identity lets SQLAlchemy know which subclass (if any) to
    # load when this row also has a matching hosts/users row.
    __mapper_args__ = {
        "polymorphic_identity": AssetType.GENERIC,
        "polymorphic_on": "asset_type",
    }


class HostORM(AssetORM):
    """The `hosts` table — extra columns specific to host assets."""

    __tablename__ = "hosts"

    asset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assets.id"), primary_key=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    operating_system: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_internet_facing: Mapped[bool] = mapped_column(default=False, index=True)

    __mapper_args__ = {
        "polymorphic_identity": AssetType.HOST,
    }


class UserORM(AssetORM):
    """The `users` table — extra columns specific to user-account assets."""

    __tablename__ = "users"

    asset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assets.id"), primary_key=True)
    is_privileged: Mapped[bool] = mapped_column(default=False, index=True)
    department: Mapped[str | None] = mapped_column(String(100), nullable=True)

    __mapper_args__ = {
        "polymorphic_identity": AssetType.USER,
    }
