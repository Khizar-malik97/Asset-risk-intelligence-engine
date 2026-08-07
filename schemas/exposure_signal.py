"""Request schema for attaching an exposure signal to an asset via the API.

Separate from schemas/asset.py since it validates a different resource
(ExposureSignal, not Asset) — same file-per-resource pattern used
throughout schemas/.
"""

from pydantic import BaseModel, Field, field_validator

from models.exposure_signal import ExposureSeverity, ExposureSignalType


class ExposureSignalAttachRequest(BaseModel):
    """Validated input for POST /assets/{asset_id}/exposure-signals."""

    signal_type: ExposureSignalType
    severity: ExposureSeverity
    description: str = Field(..., min_length=1, max_length=500)

    @field_validator("description")
    @classmethod
    def description_must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("description must not be blank or whitespace-only")
        return stripped
