"""FastAPI application entrypoint.

Run locally with:
    uvicorn api.main:app --reload

Wires together every router built so far and registers Milestone 20's
standardized error handling: exactly three handlers cover every failure
mode the API can produce, each returning the same envelope shape —

    {"error": {"code": "...", "message": "...", "details": {...}}}

1. handle_app_error — every typed exception in the codebase
   (AssetNotFoundError, DuplicateAssetError, ExposureSignalNotFoundError,
   InvalidRequestError, and any future one) inherits from
   utils.exceptions.AppError. Catching that one base class here is what
   lets a new exception type be added anywhere in the codebase without
   ever touching this file again — status_code and code live on the
   exception class itself (see utils/exceptions.py), not in a per-type
   handler.
2. handle_validation_error — FastAPI/Pydantic's own request-validation
   failures (malformed body, wrong type, missing required field) used to
   return FastAPI's default shape, which looked nothing like handler #1's
   output. This wraps that in the same envelope so a client never has to
   special-case "was it my fault or the server's" by response shape.
3. handle_unexpected_error — a deliberate last resort. Anything NOT
   raised as an AppError (a genuine bug, an unhandled edge case) still
   returns the same envelope shape and a 500, but with a generic message
   — the real exception is never shown to the caller, only logged
   server-side, so a bug can't leak internal details (stack traces, file
   paths, query text) to whoever is calling the API.
"""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from api.routers import assets, discovery, exposure_signals
from config.settings import settings
from utils.exceptions import AppError

logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.app_name,
    description="Module 12 (Asset Intelligence Module) of the AXERONIX XDR Copilot platform.",
    version="0.1.0",
)

app.include_router(assets.router)
app.include_router(exposure_signals.router)
app.include_router(discovery.router)


def _error_envelope(
    code: str, message: str, details: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Build the one error response shape every handler below returns."""
    return {"error": {"code": code, "message": message, "details": details or {}}}


@app.exception_handler(AppError)
def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_envelope(exc.code, exc.message, exc.details),
    )


@app.exception_handler(RequestValidationError)
def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    # jsonable_encoder is required, not optional, here: Pydantic v2 embeds
    # the raw underlying exception object (e.g. the ValueError a custom
    # to_domain() validator raised) inside each error dict's "ctx" field.
    # A bare json.dumps of exc.errors() blows up with "ValueError is not
    # JSON serializable" the moment a custom validator fails — this line
    # is what actually caught that during testing (see the two tests this
    # milestone updates in test_api_assets.py).
    errors = jsonable_encoder(exc.errors())
    return JSONResponse(
        status_code=422,
        content=_error_envelope(
            "validation_error",
            "The request did not match the expected format.",
            {"errors": errors},
        ),
    )


@app.exception_handler(Exception)
def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception while processing %s %s", request.method, request.url)
    return JSONResponse(
        status_code=500,
        content=_error_envelope("internal_error", "An unexpected error occurred."),
    )


@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    """Liveness check — returns 200 with no dependencies on the database
    or any other service, so it reflects only "is the process up"."""
    return {"status": "ok"}
