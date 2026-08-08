"""Unit tests for schemas/asset.py — the manual registration request schemas."""

import pytest
from pydantic import ValidationError

from models.enums import AssetCategory
from models.host import Host
from models.user import User
from schemas.asset import (
    AssetRegistrationRequest,
    HostRegistrationRequest,
    UserRegistrationRequest,
)


class TestAssetRegistrationRequest:
    def test_valid_request_constructs(self):
        request = AssetRegistrationRequest(identifier="asset-01")

        assert request.identifier == "asset-01"
        assert request.category == AssetCategory.UNCATEGORIZED
        assert request.is_critical is False

    def test_empty_identifier_rejected(self):
        with pytest.raises(ValidationError):
            AssetRegistrationRequest(identifier="")

    def test_whitespace_only_identifier_rejected(self):
        with pytest.raises(ValidationError):
            AssetRegistrationRequest(identifier="   ")

    def test_identifier_is_stripped(self):
        request = AssetRegistrationRequest(identifier="  padded-name  ")

        assert request.identifier == "padded-name"

    def test_identifier_too_long_rejected(self):
        with pytest.raises(ValidationError):
            AssetRegistrationRequest(identifier="x" * 256)

    def test_invalid_category_rejected(self):
        with pytest.raises(ValidationError):
            AssetRegistrationRequest(
                identifier="asset-02",
                category="not-a-real-category",  # type: ignore[arg-type]
            )

    def test_to_domain_produces_asset(self):
        request = AssetRegistrationRequest(
            identifier="asset-03", category=AssetCategory.SERVER, is_critical=True
        )

        asset = request.to_domain()

        assert asset.identifier == "asset-03"
        assert asset.category == AssetCategory.SERVER
        assert asset.is_critical is True


class TestHostRegistrationRequest:
    def test_valid_request_constructs(self):
        request = HostRegistrationRequest(
            identifier="web-01", ip_address="10.0.0.5", is_internet_facing=True
        )

        assert request.ip_address == "10.0.0.5"
        assert request.is_internet_facing is True

    def test_ip_address_optional(self):
        request = HostRegistrationRequest(identifier="web-02")

        assert request.ip_address is None

    def test_ip_address_explicit_none_accepted(self):
        """Distinct from test_ip_address_optional above: that test never
        passes ip_address at all, so Pydantic v2 doesn't run the field
        validator against the default (no validate_default=True here).
        This test explicitly passes None, which DOES invoke
        ip_address_must_be_valid — proving its own None-short-circuit
        branch, not just the field's default value."""
        request = HostRegistrationRequest(identifier="web-02b", ip_address=None)

        assert request.ip_address is None

    def test_whitespace_only_identifier_rejected(self):
        """HostRegistrationRequest defines its own copy of
        identifier_must_not_be_blank (not shared with
        AssetRegistrationRequest's — see schemas/asset.py) — proving it
        here, not just on AssetRegistrationRequest, closes a real gap:
        the two validators are separate code that happened to be
        identical, not the same function reused."""
        with pytest.raises(ValidationError):
            HostRegistrationRequest(identifier="   ")

    def test_invalid_ipv4_rejected(self):
        with pytest.raises(ValidationError):
            HostRegistrationRequest(identifier="web-03", ip_address="999.999.999.999")

    def test_garbage_ip_string_rejected(self):
        with pytest.raises(ValidationError):
            HostRegistrationRequest(identifier="web-04", ip_address="not-an-ip")

    def test_valid_ipv6_accepted(self):
        request = HostRegistrationRequest(identifier="web-05", ip_address="::1")

        assert request.ip_address == "::1"

    def test_operating_system_too_long_rejected(self):
        with pytest.raises(ValidationError):
            HostRegistrationRequest(identifier="web-06", operating_system="x" * 101)

    def test_to_domain_produces_host(self):
        request = HostRegistrationRequest(
            identifier="web-07",
            ip_address="10.0.0.9",
            operating_system="Ubuntu 24.04",
            is_internet_facing=True,
        )

        host = request.to_domain()

        assert isinstance(host, Host)
        assert host.ip_address == "10.0.0.9"
        assert host.operating_system == "Ubuntu 24.04"
        assert host.is_internet_facing is True


class TestUserRegistrationRequest:
    def test_valid_request_constructs(self):
        request = UserRegistrationRequest(identifier="jdoe", is_privileged=True, department="IT")

        assert request.is_privileged is True
        assert request.department == "IT"

    def test_department_optional(self):
        request = UserRegistrationRequest(identifier="jsmith")

        assert request.department is None

    def test_whitespace_only_identifier_rejected(self):
        """UserRegistrationRequest's own copy of
        identifier_must_not_be_blank — same reasoning as the equivalent
        test on TestHostRegistrationRequest above."""
        with pytest.raises(ValidationError):
            UserRegistrationRequest(identifier="   ")

    def test_department_too_long_rejected(self):
        with pytest.raises(ValidationError):
            UserRegistrationRequest(identifier="jsmith", department="x" * 101)

    def test_to_domain_produces_user(self):
        request = UserRegistrationRequest(
            identifier="admin_jdoe", is_privileged=True, department="IT"
        )

        user = request.to_domain()

        assert isinstance(user, User)
        assert user.is_privileged is True
        assert user.department == "IT"
