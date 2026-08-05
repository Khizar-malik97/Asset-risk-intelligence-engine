"""Unit tests for the ExposureSignal domain model."""

from uuid import uuid4

import pytest

from models.exposure_signal import ExposureSeverity, ExposureSignal, ExposureSignalType


class TestExposureSignal:
    def test_construct_with_valid_data(self):
        asset_id = uuid4()
        signal = ExposureSignal(
            asset_id=asset_id,
            signal_type=ExposureSignalType.INTERNET_FACING,
            severity=ExposureSeverity.HIGH,
            description="Host is reachable from the public internet on port 443",
        )

        assert signal.asset_id == asset_id
        assert signal.signal_type == ExposureSignalType.INTERNET_FACING
        assert signal.severity == ExposureSeverity.HIGH
        assert signal.id is not None
        assert signal.observed_at is not None

    def test_empty_description_is_rejected(self):
        with pytest.raises(ValueError):
            ExposureSignal(
                asset_id=uuid4(),
                signal_type=ExposureSignalType.UNPATCHED_VULNERABILITY,
                severity=ExposureSeverity.CRITICAL,
                description="",
            )

    def test_whitespace_only_description_is_rejected(self):
        with pytest.raises(ValueError):
            ExposureSignal(
                asset_id=uuid4(),
                signal_type=ExposureSignalType.UNPATCHED_VULNERABILITY,
                severity=ExposureSeverity.CRITICAL,
                description="   ",
            )

    def test_two_signals_get_different_ids(self):
        asset_id = uuid4()
        s1 = ExposureSignal(
            asset_id=asset_id,
            signal_type=ExposureSignalType.OPEN_ADMIN_PORT,
            severity=ExposureSeverity.MEDIUM,
            description="RDP open to 0.0.0.0/0",
        )
        s2 = ExposureSignal(
            asset_id=asset_id,
            signal_type=ExposureSignalType.OPEN_ADMIN_PORT,
            severity=ExposureSeverity.MEDIUM,
            description="SSH open to 0.0.0.0/0",
        )

        assert s1.id != s2.id
