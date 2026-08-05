"""Exceptions raised by the service layer.

Distinct from repositories/exceptions.py: those represent persistence-layer
facts (a row doesn't exist). These represent business-rule violations
(a registration request breaks a rule the service layer enforces) — the
distinction matters because they'll likely map to different HTTP status
codes later (404 vs 409) when Milestone 20 standardizes error handling.
"""


class DuplicateAssetError(Exception):
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

    def __init__(self, identifier: str) -> None:
        self.identifier = identifier
        super().__init__(f"An asset with identifier '{identifier}' is already registered.")
