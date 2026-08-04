"""Exceptions raised by the repository layer.

These are domain/persistence-level exceptions, distinct from the API-wide
error response standardization built in Milestone 20 — that milestone will
catch exceptions like this one and translate them into HTTP responses, but
the exception itself belongs here, close to where the failure occurs.
"""

from uuid import UUID


class AssetNotFoundError(Exception):
    """Raised when an operation targets an asset id that doesn't exist."""

    def __init__(self, asset_id: UUID) -> None:
        self.asset_id = asset_id
        super().__init__(f"No asset found with id={asset_id}")
