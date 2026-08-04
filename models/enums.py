"""Shared enumerations used across the Asset Intelligence domain.

Centralizing these here (rather than scattering string literals like
"host" or "critical" throughout the codebase) means:
  - invalid values are rejected at construction time, not discovered later
  - renaming/adding a value happens in exactly one place
  - IDEs and mypy can catch typos ("Categoty.SERVER" fails immediately)
"""

from enum import StrEnum


class AssetType(StrEnum):
    """The kind of asset a record represents."""

    GENERIC = "generic"
    HOST = "host"
    USER = "user"


class AssetCategory(StrEnum):
    """Business-meaningful classification of an asset, independent of AssetType."""

    SERVER = "server"
    WORKSTATION = "workstation"
    DOMAIN_CONTROLLER = "domain_controller"
    DATABASE_SERVER = "database_server"
    NETWORK_DEVICE = "network_device"
    ENDPOINT = "endpoint"
    SERVICE_ACCOUNT = "service_account"
    STANDARD_USER_ACCOUNT = "standard_user_account"
    PRIVILEGED_USER_ACCOUNT = "privileged_user_account"
    UNCATEGORIZED = "uncategorized"


class DiscoverySource(StrEnum):
    """Where an asset record came from."""

    MANUAL = "manual"
    DISCOVERY_PROVIDER = "discovery_provider"


class RiskLevel(StrEnum):
    """Discrete risk bucket, derived from a numeric risk score (Milestone 13)."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
