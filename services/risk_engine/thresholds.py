"""Loads and validates risk-level thresholds from config/risk_thresholds.yaml.

Mirrors weights.py's validation rigor: thresholds live in config so they
can be retuned without a code change, but the mapping from thresholds to
RiskLevel is validated strictly at load time — a misconfigured threshold
file (missing level, non-ascending values) is a startup error, not a
silent scoring bug discovered later.
"""

from pathlib import Path

import yaml

from models.enums import RiskLevel

REQUIRED_LEVELS = [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]


class RiskThresholdConfigError(Exception):
    """Raised when risk_thresholds.yaml is missing, malformed, or invalid."""


def load_risk_thresholds(path: str | Path) -> dict[RiskLevel, int]:
    """Load and validate risk-level thresholds from a YAML file.

    Expected format:
        low: 0
        medium: 20
        high: 50
        critical: 80

    A score maps to the highest level whose threshold it meets or exceeds
    (see services/risk_engine/scoring.py for the matching logic).

    Raises:
        RiskThresholdConfigError: if the file is missing; doesn't contain
            exactly the four required levels (low/medium/high/critical);
            any value isn't a non-negative integer; or values are not
            strictly ascending from low to critical.
    """
    file_path = Path(path)
    if not file_path.exists():
        raise RiskThresholdConfigError(f"Risk threshold config file not found: {file_path}")

    with file_path.open() as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, dict) or not raw:
        raise RiskThresholdConfigError(
            f"Risk threshold config must be a non-empty mapping; got: {raw!r}"
        )

    required_keys = {level.value for level in REQUIRED_LEVELS}
    provided_keys = set(raw.keys())

    missing = required_keys - provided_keys
    if missing:
        raise RiskThresholdConfigError(f"Missing required threshold level(s): {sorted(missing)}")

    unexpected = provided_keys - required_keys
    if unexpected:
        raise RiskThresholdConfigError(f"Unexpected threshold level(s): {sorted(unexpected)}")

    thresholds: dict[RiskLevel, int] = {}
    for level in REQUIRED_LEVELS:
        value = raw[level.value]
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise RiskThresholdConfigError(
                f"Threshold for '{level.value}' must be a non-negative integer; got {value!r}"
            )
        thresholds[level] = value

    ordered_values = [thresholds[level] for level in REQUIRED_LEVELS]
    if ordered_values != sorted(set(ordered_values)) or len(set(ordered_values)) != len(
        ordered_values
    ):
        raise RiskThresholdConfigError(
            f"Thresholds must be strictly ascending from low to critical; got: "
            f"{ {level.value: thresholds[level] for level in REQUIRED_LEVELS} }"
        )

    return thresholds
