"""Database engine and session management.

Provides a single configured SQLAlchemy engine (built from settings.database_url)
and a session factory used throughout the repository layer (Milestone 7).
"""

from collections.abc import Generator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from config.settings import settings


def _build_engine() -> Engine:
    """Create the SQLAlchemy engine.

    SQLite needs `check_same_thread=False` to be usable across the async
    request lifecycle FastAPI uses; PostgreSQL doesn't need or accept this
    argument, so it's applied conditionally.
    """
    connect_args = {}
    if settings.database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    return create_engine(settings.database_url, connect_args=connect_args)


engine: Engine = _build_engine()

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db_session() -> Generator[Session, None, None]:
    """Yield a database session, guaranteeing it's closed afterward.

    Intended for use as a FastAPI dependency (Milestone 19) via
    `Depends(get_db_session)`, and directly in scripts/tests via a `with`-style
    loop over this generator.
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
