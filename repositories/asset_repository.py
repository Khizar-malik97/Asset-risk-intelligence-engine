"""SQLAlchemy-backed implementation of AssetRepositoryInterface.

This is the ONLY class in the codebase that runs SQL. Everything above it
(services, API) works through the interface and never imports SQLAlchemy.
"""

from uuid import UUID

from sqlalchemy.orm import Session

from models.asset import Asset
from models.orm.asset_orm import AssetORM
from repositories.exceptions import AssetNotFoundError
from repositories.interfaces import AssetRepositoryInterface
from repositories.mappers import domain_to_orm, orm_to_domain


class SQLAlchemyAssetRepository(AssetRepositoryInterface):
    """Persists Asset/Host/User domain objects via SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, asset: Asset) -> Asset:
        orm_asset = domain_to_orm(asset)
        self._session.add(orm_asset)
        self._session.commit()
        self._session.refresh(orm_asset)
        return orm_to_domain(orm_asset)

    def get_by_id(self, asset_id: UUID) -> Asset | None:
        orm_asset = self._session.get(AssetORM, asset_id)
        if orm_asset is None:
            return None
        return orm_to_domain(orm_asset)

    def list_all(self) -> list[Asset]:
        orm_assets = self._session.query(AssetORM).all()
        return [orm_to_domain(orm_asset) for orm_asset in orm_assets]

    def update(self, asset: Asset) -> Asset:
        existing = self._session.get(AssetORM, asset.id)
        if existing is None:
            raise AssetNotFoundError(asset.id)

        # Re-map to a fresh ORM instance and merge, rather than mutating
        # `existing` field-by-field — this keeps the mapper as the single
        # source of truth for the domain<->ORM field mapping, instead of
        # duplicating that knowledge here.
        updated_orm = domain_to_orm(asset)
        merged = self._session.merge(updated_orm)
        self._session.commit()
        self._session.refresh(merged)
        return orm_to_domain(merged)

    def delete(self, asset_id: UUID) -> None:
        existing = self._session.get(AssetORM, asset_id)
        if existing is None:
            raise AssetNotFoundError(asset_id)

        self._session.delete(existing)
        self._session.commit()
