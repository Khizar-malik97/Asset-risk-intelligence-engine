"""Repository for ExposureSignal persistence.

Follows the same interface + SQLAlchemy-implementation pattern as
AssetRepository (Milestone 7) — see docs/architecture.md ADR-002.
"""

from abc import ABC, abstractmethod
from uuid import UUID

from sqlalchemy.orm import Session

from models.exposure_signal import ExposureSignal
from models.orm.exposure_signal_orm import ExposureSignalORM


class ExposureSignalRepositoryInterface(ABC):
    """Storage abstraction for exposure signals."""

    @abstractmethod
    def add(self, signal: ExposureSignal) -> ExposureSignal: ...

    @abstractmethod
    def list_for_asset(self, asset_id: UUID) -> list[ExposureSignal]: ...

    @abstractmethod
    def remove(self, signal_id: UUID) -> None: ...


def _to_domain(row: ExposureSignalORM) -> ExposureSignal:
    return ExposureSignal(
        id=row.id,
        asset_id=row.asset_id,
        signal_type=row.signal_type,  # type: ignore[arg-type]
        severity=row.severity,  # type: ignore[arg-type]
        description=row.description,
        observed_at=row.observed_at,
    )


def _to_orm(signal: ExposureSignal) -> ExposureSignalORM:
    return ExposureSignalORM(
        id=signal.id,
        asset_id=signal.asset_id,
        signal_type=signal.signal_type,
        severity=signal.severity,
        description=signal.description,
        observed_at=signal.observed_at,
    )


class SQLAlchemyExposureSignalRepository(ExposureSignalRepositoryInterface):
    """SQLAlchemy-backed implementation of ExposureSignalRepositoryInterface."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, signal: ExposureSignal) -> ExposureSignal:
        row = _to_orm(signal)
        self._session.add(row)
        self._session.commit()
        self._session.refresh(row)
        return _to_domain(row)

    def list_for_asset(self, asset_id: UUID) -> list[ExposureSignal]:
        rows = (
            self._session.query(ExposureSignalORM)
            .filter_by(asset_id=asset_id)
            .order_by(ExposureSignalORM.observed_at.desc())
            .all()
        )
        return [_to_domain(row) for row in rows]

    def remove(self, signal_id: UUID) -> None:
        row = self._session.get(ExposureSignalORM, signal_id)
        if row is None:
            raise ValueError(f"ExposureSignal {signal_id} not found.")
        self._session.delete(row)
        self._session.commit()
