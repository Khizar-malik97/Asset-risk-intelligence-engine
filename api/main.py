"""FastAPI application entrypoint.

Run locally with:
    uvicorn api.main:app --reload

Wires together every router built in this milestone and registers two
global exception handlers for the service layer's own well-defined
exceptions — DuplicateAssetError and AssetNotFoundError mean the same
thing (409, 404) no matter which endpoint raises them, so handling them
globally here avoids every router repeating identical try/except blocks.
This is deliberately minimal: a fully standardized error-response body
(consistent shape, error codes, etc. across every failure mode) is
Milestone 20's job — this milestone only needs correct status codes.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from api.routers import assets, discovery, exposure_signals
from config.settings import settings
from repositories.exceptions import AssetNotFoundError
from services.exceptions import DuplicateAssetError

app = FastAPI(
    title=settings.app_name,
    description="Module 12 (Asset Intelligence Module) of the AXERONIX XDR Copilot platform.",
    version="0.1.0",
)

app.include_router(assets.router)
app.include_router(exposure_signals.router)
app.include_router(discovery.router)


@app.exception_handler(DuplicateAssetError)
def handle_duplicate_asset(request: Request, exc: DuplicateAssetError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(AssetNotFoundError)
def handle_asset_not_found(request: Request, exc: AssetNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    """Liveness check — returns 200 with no dependencies on the database
    or any other service, so it reflects only "is the process up"."""
    return {"status": "ok"}
