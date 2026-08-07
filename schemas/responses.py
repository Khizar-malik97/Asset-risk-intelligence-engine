"""API response schemas — the outbound counterpart to the request schemas
in schemas/asset.py and schemas/exposure_signal.py.

Deliberately separate Pydantic models rather than returning domain
dataclasses directly from routers: this keeps the API's response
*contract* explicit and documented in OpenAPI, independent of internal
domain-model changes — the same domain/API separation principle ADR-005
(docs/architecture.md) applies to requests.

AssetResponse is deliberately a single FLATTENED model covering Asset,
Host, and User rather than three separate response types with a
discriminated union. Endpoints that return a mixed list (GET /assets,
search) need one consistent shape; type-specific fields (ip_address,
is_privileged, etc.) are simply None on rows where they don't apply.
`from_attributes=True` lets Pydantic build this straight off whichever
domain object (Asset/Host/User) a service returns, reading only the
attributes that exist. A stricter discriminated-union response is a
reasonable future refinement, not a Milestone 19 requirement.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from models.enums import AssetCategory, AssetType, DiscoverySource, RiskLevel
from models.exposure_signal import ExposureSeverity, ExposureSignalType


class AssetResponse(BaseModel):
    """Flattened response shape covering Asset, Host, and User uniformly."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    identifier: str
    asset_type: AssetType
    category: AssetCategory
    is_critical: bool
    discovery_source: DiscoverySource
    first_seen: datetime
    last_seen: datetime

    # Host-specific — populated only when asset_type == "host"
    ip_address: str | None = None
    operating_system: str | None = None
    is_internet_facing: bool | None = None

    # User-specific — populated only when asset_type == "user"
    is_privileged: bool | None = None
    department: str | None = None


class ExposureSignalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    asset_id: UUID
    signal_type: ExposureSignalType
    severity: ExposureSeverity
    description: str
    observed_at: datetime


class RiskFactorResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    factor_name: str
    weight_applied: int
    triggered: bool
    reason: str


class RiskScoreResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    asset_id: UUID
    total_score: int
    risk_level: RiskLevel
    factor_results: list[RiskFactorResultResponse]


class ConfidenceScoreResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    asset_id: UUID
    confidence_score: int
    source_reliability_score: int
    recency_score: int
    reason: str


class DiscoveryRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    assets: list[AssetResponse]
    assets_by_provider: dict[str, int]


class ReconciliationGroupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    identifier: str
    canonical_asset: AssetResponse
    duplicates_removed: int


class ReconciliationRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    groups_reconciled: list[ReconciliationGroupResponse]
    total_duplicates_removed: int
