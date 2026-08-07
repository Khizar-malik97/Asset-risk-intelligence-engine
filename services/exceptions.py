"""Exceptions raised by the service layer.

Distinct from repositories/exceptions.py: those represent persistence-layer
facts (a row doesn't exist). These represent business-rule violations (a
registration request breaks a rule the service layer enforces). As of
Milestone 20, both inherit from utils.exceptions.AppError subclasses so
api/main.py's single AppError handler maps each to the right status code
(404 vs 409) via `status_code` on the exception class, not per-raise-site
logic.
"""

from utils.exceptions import ConflictError


class DuplicateAssetError(ConflictError):
    """Raised when manually registering an asset whose identifier already
    exists in the inventory.

    Scope note: this check is exact-identifier-match only, and applies to
    manual registration (Milestone 9). It is NOT the same problem the
    Discovery Reconciliation engine (Milestone 16) solves — reconciliation
    merges partial, possibly-conflicting records arriving from *multiple
    automated discovery sources* describing the same real-world asset.
    This is the simpler case: reject an obvious accidental duplicate at
    the moment a human registers it.
    """

    code = "duplicate_asset"

    def __init__(self, identifier: str) -> None:
        self.identifier = identifier
        super().__init__(
            f"An asset with identifier '{identifier}' is already registered.",
            details={"identifier": identifier},
        )
