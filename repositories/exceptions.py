"""Exceptions raised by the repository layer.

These are domain/persistence-level exceptions. As of Milestone 20 they
inherit from utils.exceptions.NotFoundError, so api/main.py's single
AppError handler picks them up automatically — no per-exception handler,
no per-router try/except. The exception itself still lives here, close to
where the failure occurs; only its base class changed.
"""

from uuid import UUID

from utils.exceptions import NotFoundError


class AssetNotFoundError(NotFoundError):
    """Raised when an operation targets an asset id that doesn't exist."""

    code = "asset_not_found"

    def __init__(self, asset_id: UUID) -> None:
        self.asset_id = asset_id
        super().__init__(f"No asset found with id={asset_id}", details={"asset_id": str(asset_id)})


class ExposureSignalNotFoundError(NotFoundError):
    """Raised when an operation targets an exposure signal id that
    doesn't exist. Replaces the bare ValueError this used to be (see
    exposure_signal_repository.py) — that meant api/routers/exposure_signals.py
    needed its own local try/except, which this milestone removes."""

    code = "exposure_signal_not_found"

    def __init__(self, signal_id: UUID) -> None:
        self.signal_id = signal_id
        super().__init__(
            f"No exposure signal found with id={signal_id}",
            details={"signal_id": str(signal_id)},
        )
