"""Loads and validates risk factor weights from config/risk_weights.yaml.

Weights live in config, not code, so a security team can retune scoring
without a code change or redeploy — while the *conditions* each factor
checks stay in factors.py, reviewed like any other code change.
"""

from collections.abc import Mapping
from pathlib import Path

import yaml

from services.risk_engine.base import RiskFactor


class RiskWeightConfigError(Exception):
    """Raised when risk_weights.yaml is missing, malformed, or invalid."""


def load_risk_weights(path: str | Path) -> dict[str, int]:
    """Load and validate factor weights from a YAML file.

    Expected format:
        critical_asset_flag: 30
        internet_facing: 25
        unpatched_vulnerability: 15
        privileged_account: 20

    Raises:
        RiskWeightConfigError: if the file is missing, isn't a flat mapping
            of factor name -> non-negative integer, or is empty.
    """
    file_path = Path(path)
    if not file_path.exists():
        raise RiskWeightConfigError(f"Risk weight config file not found: {file_path}")

    with file_path.open() as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, dict) or not raw:
        raise RiskWeightConfigError(
            f"Risk weight config must be a non-empty mapping of factor name to "
            f"weight; got: {raw!r}"
        )

    weights: dict[str, int] = {}
    for factor_name, weight in raw.items():
        if not isinstance(factor_name, str) or not factor_name.strip():
            raise RiskWeightConfigError(f"Invalid factor name in config: {factor_name!r}")
        if not isinstance(weight, int) or isinstance(weight, bool) or weight < 0:
            raise RiskWeightConfigError(
                f"Weight for factor '{factor_name}' must be a non-negative integer; "
                f"got {weight!r}"
            )
        weights[factor_name] = weight

    return weights


def build_factors(
    weights: dict[str, int],
    registry: Mapping[str, type[RiskFactor]] | None = None,
) -> list[RiskFactor]:
    """Instantiate every registered factor using its configured weight.

    Args:
        weights: factor name -> weight, as returned by load_risk_weights().
        registry: factor registry to build from; defaults to the real
            get_registered_factors() registry if not provided (tests pass
            their own to avoid depending on global registration order).
            Typed as Mapping (covariant) rather than dict (invariant) so a
            caller can pass a dict[str, type[SomeSpecificFactor]] without a
            type error.

    Raises:
        RiskWeightConfigError: if a registered factor has no weight entry
            in the config, or the config has a weight for an unregistered
            factor name (catches typos in risk_weights.yaml immediately,
            rather than silently ignoring them).
    """
    if registry is None:
        from services.risk_engine.registry import get_registered_factors

        registry = get_registered_factors()

    registered_names = set(registry.keys())
    configured_names = set(weights.keys())

    missing = registered_names - configured_names
    if missing:
        raise RiskWeightConfigError(
            f"No weight configured for registered factor(s): {sorted(missing)}"
        )

    unknown = configured_names - registered_names
    if unknown:
        raise RiskWeightConfigError(
            f"Weight config references unregistered factor(s): {sorted(unknown)}"
        )

    return [factor_class(weight=weights[name]) for name, factor_class in registry.items()]
