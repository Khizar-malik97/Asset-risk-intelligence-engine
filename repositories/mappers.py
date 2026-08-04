"""Converts between domain models (models/asset.py, host.py, user.py) and
ORM models (models/orm/asset_orm.py).

This is the ONLY place in the codebase that should know both "shapes" at
once. Everywhere else, code works with either domain objects (business
logic) or ORM objects (this repository's internals) — never both.
"""

from models.asset import Asset
from models.host import Host
from models.orm.asset_orm import AssetORM, HostORM, UserORM
from models.user import User


def domain_to_orm(asset: Asset) -> AssetORM:
    """Convert a domain Asset/Host/User into its corresponding ORM row."""
    if isinstance(asset, Host):
        return HostORM(
            id=asset.id,
            asset_id=asset.id,
            identifier=asset.identifier,
            category=asset.category,
            is_critical=asset.is_critical,
            discovery_source=asset.discovery_source,
            first_seen=asset.first_seen,
            last_seen=asset.last_seen,
            ip_address=asset.ip_address,
            operating_system=asset.operating_system,
            is_internet_facing=asset.is_internet_facing,
        )
    if isinstance(asset, User):
        return UserORM(
            id=asset.id,
            asset_id=asset.id,
            identifier=asset.identifier,
            category=asset.category,
            is_critical=asset.is_critical,
            discovery_source=asset.discovery_source,
            first_seen=asset.first_seen,
            last_seen=asset.last_seen,
            is_privileged=asset.is_privileged,
            department=asset.department,
        )
    return AssetORM(
        id=asset.id,
        identifier=asset.identifier,
        asset_type=asset.asset_type,
        category=asset.category,
        is_critical=asset.is_critical,
        discovery_source=asset.discovery_source,
        first_seen=asset.first_seen,
        last_seen=asset.last_seen,
    )


def orm_to_domain(orm_asset: AssetORM) -> Asset:
    """Convert an ORM row back into its corresponding domain object.

    Relies on SQLAlchemy's polymorphic loading already having given us the
    correct subclass (HostORM/UserORM) — see AssetORM.__mapper_args__.
    """
    if isinstance(orm_asset, HostORM):
        host = Host(
            identifier=orm_asset.identifier,
            category=orm_asset.category,
            is_critical=orm_asset.is_critical,
            discovery_source=orm_asset.discovery_source,
            id=orm_asset.id,
            first_seen=orm_asset.first_seen,
            last_seen=orm_asset.last_seen,
            ip_address=orm_asset.ip_address,
            operating_system=orm_asset.operating_system,
            is_internet_facing=orm_asset.is_internet_facing,
        )
        return host

    if isinstance(orm_asset, UserORM):
        user = User(
            identifier=orm_asset.identifier,
            category=orm_asset.category,
            is_critical=orm_asset.is_critical,
            discovery_source=orm_asset.discovery_source,
            id=orm_asset.id,
            first_seen=orm_asset.first_seen,
            last_seen=orm_asset.last_seen,
            is_privileged=orm_asset.is_privileged,
            department=orm_asset.department,
        )
        return user

    return Asset(
        identifier=orm_asset.identifier,
        asset_type=orm_asset.asset_type,
        category=orm_asset.category,
        is_critical=orm_asset.is_critical,
        discovery_source=orm_asset.discovery_source,
        id=orm_asset.id,
        first_seen=orm_asset.first_seen,
        last_seen=orm_asset.last_seen,
    )
