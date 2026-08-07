"""Request schemas for manual asset registration.

These are deliberately separate from the domain models in models/asset.py,
models/host.py, and models/user.py (see docs/architecture.md ADR-005 for
the domain-model/API-schema separation this follows).

Why validation lives here and not (only) on the domain models:
    The domain models enforce the bare minimum invariant needed for the
    object to make sense at all (a non-empty identifier). These schemas
    enforce the *input-validation* rules specific to a human filling out a
    manual registration request: length limits matching the database
    columns, a well-formed IP address, valid enum values, etc. A future
    programmatic caller building a Host directly (e.g. the Discovery
    engine, Milestone 12) is not required to go through these schemas —
    but anything entering through manual registration is.

Each schema has a `to_domain()` method that converts a validated request
into the corresponding domain object, so the service layer only ever
works with domain models, never with these request schemas directly.
"""

import ipaddress

from pydantic import BaseModel, Field, field_validator

from models.asset import Asset
from models.enums import AssetCategory, DiscoverySource
from models.host import Host
from models.user import User


class AssetRegistrationRequest(BaseModel):
    """Validated input for registering a generic (non-host, non-user) asset."""

    identifier: str = Field(..., min_length=1, max_length=255)
    category: AssetCategory = AssetCategory.UNCATEGORIZED
    is_critical: bool = False

    @field_validator("identifier")
    @classmethod
    def identifier_must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("identifier must not be blank or whitespace-only")
        return stripped

    def to_domain(self) -> Asset:
        return Asset(
            identifier=self.identifier,
            category=self.category,
            is_critical=self.is_critical,
            discovery_source=DiscoverySource.MANUAL,
        )


class HostRegistrationRequest(BaseModel):
    """Validated input for manually registering a host asset."""

    identifier: str = Field(..., min_length=1, max_length=255)
    category: AssetCategory = AssetCategory.UNCATEGORIZED
    is_critical: bool = False
    ip_address: str | None = Field(default=None)
    operating_system: str | None = Field(default=None, max_length=100)
    is_internet_facing: bool = False

    @field_validator("identifier")
    @classmethod
    def identifier_must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("identifier must not be blank or whitespace-only")
        return stripped

    @field_validator("ip_address")
    @classmethod
    def ip_address_must_be_valid(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            ipaddress.ip_address(value)
        except ValueError as exc:
            raise ValueError(f"'{value}' is not a valid IPv4 or IPv6 address") from exc
        return value

    def to_domain(self) -> Host:
        return Host(
            identifier=self.identifier,
            category=self.category,
            is_critical=self.is_critical,
            discovery_source=DiscoverySource.MANUAL,
            ip_address=self.ip_address,
            operating_system=self.operating_system,
            is_internet_facing=self.is_internet_facing,
        )


class UserRegistrationRequest(BaseModel):
    """Validated input for manually registering a user-account asset."""

    identifier: str = Field(..., min_length=1, max_length=255)
    category: AssetCategory = AssetCategory.UNCATEGORIZED
    is_critical: bool = False
    is_privileged: bool = False
    department: str | None = Field(default=None, max_length=100)

    @field_validator("identifier")
    @classmethod
    def identifier_must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("identifier must not be blank or whitespace-only")
        return stripped

    def to_domain(self) -> User:
        return User(
            identifier=self.identifier,
            category=self.category,
            is_critical=self.is_critical,
            discovery_source=DiscoverySource.MANUAL,
            is_privileged=self.is_privileged,
            department=self.department,
        )


class CategoryAssignmentRequest(BaseModel):
    """Validated input for the category-assignment endpoint
    (PATCH /assets/{asset_id}/category, Milestone 19) — a single-field
    schema rather than reusing a registration request, since assigning a
    category to an existing asset has nothing to validate beyond the
    category value itself."""

    category: AssetCategory
