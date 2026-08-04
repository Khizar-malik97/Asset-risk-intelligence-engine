"""SQLAlchemy declarative base shared by every ORM model in this package."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base. All ORM models inherit from this."""
