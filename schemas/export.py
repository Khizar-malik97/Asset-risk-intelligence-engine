"""Response schema for the JSON export endpoint (Milestone 21).

AssetExportSchema deliberately mirrors AssetResponse's fields (schemas/
responses.py) rather than importing and reusing that class directly.
That's a conscious choice, not duplication-for-its-own-sake:
AssetResponse is the live contract for GET /assets and is free to evolve
alongside the internal domain model, while an *export* schema is a
stability contract for offline consumers who may load an exported file
on a schedule the API's own version history has no visibility into.
Coupling the two means a future AssetResponse change could silently
change the export format underneath someone who already saved a file to
disk. `schema_version` exists for exactly this reason: if this schema
ever does need to change shape, that's a version bump here, not a silent
break for whoever already has last week's export.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from models.enums import AssetCategory, AssetType, DiscoverySource


class AssetExportSchema(BaseModel):
    """One asset's exported shape. Field set intentionally matches
    AssetResponse today — they're allowed to diverge later without
    either one having to change to match the other."""

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


class ExportResponse(BaseModel):
    """The full export document. `asset_count` is redundant with
    `len(assets)` by construction, but included explicitly so a consumer
    reading a large export can sanity-check counts without necessarily
    parsing the whole `assets` array first."""

    schema_version: int
    exported_at: datetime
    asset_count: int
    assets: list[AssetExportSchema]
