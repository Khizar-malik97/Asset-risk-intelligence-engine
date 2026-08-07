"""Application-wide exception hierarchy.

Every exception that should produce a specific, structured HTTP error
response inherits from AppError. This is the one piece of infrastructure
Milestone 20 adds: a shared base so api/main.py needs exactly one handler
for "any AppError", instead of one handler per exception type (the
Milestone 19 approach, which didn't scale — see api/main.py's docstring
before this milestone).

Each AppError carries:
    - a stable, machine-readable `code` (snake_case) — safe for a future
      API consumer (Modules 2/8/9) to branch on, since it won't change
      even if `message` wording is later reworded for clarity.
    - a human-readable `message` — safe to show directly to a caller.
    - an HTTP `status_code` — set once per exception class, not per
      raise site, so the mapping from "kind of error" to "status code"
      lives in exactly one place.
    - optional `details` — structured extra context (e.g. which field
      failed validation). Empty dict by default.

Three concrete subclasses cover every error this API currently raises.
Adding a new failure mode later means adding one more small subclass
here — never touching api/main.py's handlers.
"""

from typing import Any


class AppError(Exception):
    """Base class for every exception that should produce a structured,
    typed HTTP error response. Do not raise this directly — raise one of
    the subclasses below (or add a new one) so `status_code` is always
    set meaningfully."""

    status_code: int = 500
    code: str = "internal_error"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        self.message = message
        self.details = details or {}
        super().__init__(message)


class NotFoundError(AppError):
    """The requested resource does not exist. Maps to HTTP 404."""

    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    """The request conflicts with existing state (e.g. a duplicate
    identifier). Maps to HTTP 409."""

    status_code = 409
    code = "conflict"


class InvalidRequestError(AppError):
    """The request is well-formed JSON/schema-wise (FastAPI's own
    validation already handles that) but violates a business rule that
    only the service layer can check — e.g. a search filter that requires
    a dependency the caller's request didn't provide the context for.
    Maps to HTTP 400."""

    status_code = 400
    code = "invalid_request"
