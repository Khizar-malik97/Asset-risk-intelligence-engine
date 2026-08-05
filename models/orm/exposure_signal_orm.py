"""SQLAlchemy ORM model for the `exposure_signals` table.

One asset can have many exposure signals (one-to-many), linked by asset_id.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from models.orm.base import Base


class ExposureSignalORM(Base):
    """Database row representing a single ExposureSignal."""

    __tablename__ = "exposure_signals"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    signal_type: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    def __repr__(self) -> str:
        return (
            f"<ExposureSignalORM id={self.id} asset_id={self.asset_id} "
            f"type={self.signal_type} severity={self.severity}>"
        )
