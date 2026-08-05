"""Unit tests for services/risk_engine/thresholds.py."""

from pathlib import Path

import pytest

from models.enums import RiskLevel
from services.risk_engine.thresholds import RiskThresholdConfigError, load_risk_thresholds


def _write_yaml(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "thresholds.yaml"
    path.write_text(content)
    return path


class TestLoadRiskThresholds:
    def test_load_valid_thresholds(self, tmp_path: Path) -> None:
        path = _write_yaml(tmp_path, "low: 0\nmedium: 20\nhigh: 50\ncritical: 80\n")

        result = load_risk_thresholds(path)

        assert result == {
            RiskLevel.LOW: 0,
            RiskLevel.MEDIUM: 20,
            RiskLevel.HIGH: 50,
            RiskLevel.CRITICAL: 80,
        }

    def test_missing_file_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(RiskThresholdConfigError, match="not found"):
            load_risk_thresholds(tmp_path / "does_not_exist.yaml")

    def test_empty_file_rejected(self, tmp_path: Path) -> None:
        path = _write_yaml(tmp_path, "")

        with pytest.raises(RiskThresholdConfigError):
            load_risk_thresholds(path)

    def test_missing_level_rejected(self, tmp_path: Path) -> None:
        path = _write_yaml(tmp_path, "low: 0\nmedium: 20\nhigh: 50\n")

        with pytest.raises(RiskThresholdConfigError, match="Missing"):
            load_risk_thresholds(path)

    def test_unexpected_level_rejected(self, tmp_path: Path) -> None:
        path = _write_yaml(tmp_path, "low: 0\nmedium: 20\nhigh: 50\ncritical: 80\nextreme: 100\n")

        with pytest.raises(RiskThresholdConfigError, match="Unexpected"):
            load_risk_thresholds(path)

    def test_non_integer_value_rejected(self, tmp_path: Path) -> None:
        path = _write_yaml(tmp_path, "low: 0\nmedium: twenty\nhigh: 50\ncritical: 80\n")

        with pytest.raises(RiskThresholdConfigError):
            load_risk_thresholds(path)

    def test_negative_value_rejected(self, tmp_path: Path) -> None:
        path = _write_yaml(tmp_path, "low: -5\nmedium: 20\nhigh: 50\ncritical: 80\n")

        with pytest.raises(RiskThresholdConfigError):
            load_risk_thresholds(path)

    def test_non_ascending_values_rejected(self, tmp_path: Path) -> None:
        path = _write_yaml(tmp_path, "low: 0\nmedium: 60\nhigh: 50\ncritical: 80\n")

        with pytest.raises(RiskThresholdConfigError, match="ascending"):
            load_risk_thresholds(path)

    def test_duplicate_values_rejected(self, tmp_path: Path) -> None:
        path = _write_yaml(tmp_path, "low: 0\nmedium: 20\nhigh: 20\ncritical: 80\n")

        with pytest.raises(RiskThresholdConfigError, match="ascending"):
            load_risk_thresholds(path)

    def test_real_config_file_loads_successfully(self) -> None:
        """The actual config/risk_thresholds.yaml shipped with the project
        must itself pass every validation rule."""
        result = load_risk_thresholds("config/risk_thresholds.yaml")

        assert set(result.keys()) == {
            RiskLevel.LOW,
            RiskLevel.MEDIUM,
            RiskLevel.HIGH,
            RiskLevel.CRITICAL,
        }
