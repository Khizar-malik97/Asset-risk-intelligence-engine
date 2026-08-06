"""User Inventory Service.

Mirrors HostInventoryService exactly, scoped to User assets instead of
Host. See host_inventory_service.py for the full rationale — same thin
wrapper pattern, no duplicated persistence logic.
"""

from typing import cast
from uuid import UUID

from logging_.logger import get_logger
from models.user import User
from repositories.interfaces import AssetRepositoryInterface
from services.exceptions import DuplicateAssetError

logger = get_logger(__name__)


class UserInventoryService:
    """Use-case layer scoped specifically to User assets."""

    def __init__(self, repository: AssetRepositoryInterface) -> None:
        self._repository = repository

    def register_user(self, user: User) -> User:
        """Register a new user account, rejecting a duplicate identifier.

        Raises:
            DuplicateAssetError: if a user with this identifier already exists.
        """
        existing = self._repository.get_by_identifier(user.identifier)
        if existing is not None:
            logger.info(
                "User registration rejected: duplicate identifier",
                extra={"identifier": user.identifier, "existing_asset_id": str(existing.id)},
            )
            raise DuplicateAssetError(user.identifier)

        saved = self._repository.add(user)
        logger.info(
            "User registered", extra={"asset_id": str(saved.id), "identifier": saved.identifier}
        )
        assert isinstance(saved, User)
        return saved

    def get_user(self, asset_id: UUID) -> User | None:
        """Retrieve a user by id. Returns None both when nothing exists at
        that id AND when the id belongs to a non-User asset."""
        asset = self._repository.get_by_id(asset_id)
        if isinstance(asset, User):
            return asset
        return None

    def list_users(self) -> list[User]:
        """Return every user account in the inventory."""
        users = self._repository.list_users()
        assert all(isinstance(u, User) for u in users)
        return cast(list[User], users)
