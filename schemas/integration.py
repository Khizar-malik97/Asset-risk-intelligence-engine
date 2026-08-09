"""Read-only integration schemas (Milestone 26).

These are a deliberately separate, LEANER contract from schemas/responses.py's
AssetResponse — same reasoning schemas/export.py already documents for
AssetExportSchema: this module's job is being a stable dependency other
modules (2, 8, 9) can build against, so its shape should carry only what a
downstream consumer of asset CONTEXT actually needs (identity, criticality,
risk, confidence), not every field of the full CRUD resource. Full asset
detail is still available via GET /assets/{id} for anyone who needs it.
"""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from models.enums import AssetCategory, AssetType, RiskLevel


class AssetContext(BaseModel):
    """The lean, per-asset payload every integration endpoint below
    returns. Risk and confidence are always computed fresh — see
    api/routers/assets.py's risk/confidence endpoints for why nothing
    about either is ever cached or persisted; this endpoint makes the
    same guarantee."""

    model_config = ConfigDict(from_attributes=True)

    asset_id: UUID
    identifier: str
    asset_type: AssetType
    category: AssetCategory
    is_critical: bool
    risk_score: int
    risk_level: RiskLevel
    confidence_score: int


class BulkContextRequest(BaseModel):
    """Request body for POST /integration/assets/context. Batched on
    purpose: a consumer like Module 2 (Event Correlation Engine)
    enriching a burst of alerts needs context for many assets at once —
    one request here replaces what would otherwise be one
    GET /assets/{id}/risk plus one GET /assets/{id}/confidence call PER
    asset, which doesn't scale for a module correlating events in real
    time."""

    asset_ids: list[UUID] = Field(..., min_length=1, max_length=500)


class BulkContextResponse(BaseModel):
    """Response for POST /integration/assets/context.

    `found` and `not_found` are kept separate rather than silently
    dropping missing ids — a caller batch-enriching alerts needs to know
    which asset ids it asked about don't exist in this module's
    inventory (e.g. an alert referencing an asset Module 1 hasn't
    reported yet), not just get back fewer results than it asked for."""

    found: list[AssetContext]
    not_found: list[UUID]


class CategoryCount(BaseModel):
    category: AssetCategory
    count: int


class RiskLevelCount(BaseModel):
    risk_level: RiskLevel
    count: int


class InventorySummary(BaseModel):
    """Aggregate counts for GET /integration/summary — the shape a
    dashboard consumer (Module 9) actually wants: rolled-up numbers, not
    every asset record. `by_risk_level` requires scoring every asset on
    demand (same cost GET /assets?risk_level=... already pays, see
    services/inventory/search.py) since risk is never persisted."""

    total_assets: int
    critical_assets: int
    by_category: list[CategoryCount]
    by_risk_level: list[RiskLevelCount]
