"""Host Inventory Service.

A thin, type-scoped wrapper around AssetRepositoryInterface for host
assets specifically. Deliberately does NOT reimplement persistence logic —
it delegates to the same repository AssetInventoryService uses, narrowing
the type at the API surface (register_host takes/returns Host, not the
generic Asset) so callers working specifically with hosts don't need to
isinstance-check or cast results themselves.
"""

from typing import cast
from uuid import UUID

from logging_.logger import get_logger
from models.host import Host
from repositories.interfaces import AssetRepositoryInterface
from services.exceptions import DuplicateAssetError

logger = get_logger(__name__)


class HostInventoryService:
    """Use-case layer scoped specifically to Host assets."""

    def __init__(self, repository: AssetRepositoryInterface) -> None:
        self._repository = repository

    def register_host(self, host: Host) -> Host:
        """Register a new host, rejecting a duplicate identifier — same
        rule as AssetInventoryService.register_asset().

        Raises:
            DuplicateAssetError: if a host with this identifier already exists.
        """
        existing = self._repository.get_by_identifier(host.identifier)
        if existing is not None:
            logger.info(
                "Host registration rejected: duplicate identifier",
                extra={"identifier": host.identifier, "existing_asset_id": str(existing.id)},
            )
            raise DuplicateAssetError(host.identifier)

        saved = self._repository.add(host)
        logger.info(
            "Host registered", extra={"asset_id": str(saved.id), "identifier": saved.identifier}
        )
        # Safe: repository.add() returns whatever type was passed in
        # (mappers.py preserves the concrete subclass round-trip).
        assert isinstance(saved, Host)
        return saved

    def get_host(self, asset_id: UUID) -> Host | None:
        """Retrieve a host by id. Returns None both when nothing exists at
        that id AND when the id belongs to a non-Host asset — callers
        working through this service only ever see hosts."""
        asset = self._repository.get_by_id(asset_id)
        if isinstance(asset, Host):
            return asset
        return None

    def list_hosts(self) -> list[Host]:
        """Return every host in the inventory."""
        hosts = self._repository.list_hosts()
        assert all(isinstance(h, Host) for h in hosts)
        return cast(list[Host], hosts)
