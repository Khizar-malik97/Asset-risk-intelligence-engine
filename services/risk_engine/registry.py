"""Risk factor registry: auto-discovery via decorator registration.

Mirrors the pattern used by the platform's Correlation Engine rule engine
(@register_rule) — a new RiskFactor subclass registers itself just by being
decorated, with no central "list of all factors" to remember to update.
"""

from services.risk_engine.base import RiskFactor

_FACTOR_REGISTRY: dict[str, type[RiskFactor]] = {}


def register_factor(factor_class: type[RiskFactor]) -> type[RiskFactor]:
    """Class decorator: registers a RiskFactor subclass by its `name`.

    Usage:
        @register_factor
        class MyFactor(RiskFactor):
            name = "my_factor"
            ...

    Raises:
        ValueError: if `name` is missing/empty, or already registered by
            another factor class (prevents silent weight-config collisions).
    """
    name = getattr(factor_class, "name", None)
    if not name:
        raise ValueError(
            f"{factor_class.__name__} must define a non-empty `name` before registration."
        )
    if name in _FACTOR_REGISTRY and _FACTOR_REGISTRY[name] is not factor_class:
        raise ValueError(
            f"Risk factor name '{name}' is already registered to "
            f"{_FACTOR_REGISTRY[name].__name__}; cannot also register it to "
            f"{factor_class.__name__}. Factor names must be unique."
        )
    _FACTOR_REGISTRY[name] = factor_class
    return factor_class


def get_registered_factors() -> dict[str, type[RiskFactor]]:
    """Return a copy of the current factor registry (name -> class)."""
    return dict(_FACTOR_REGISTRY)


def clear_registry() -> None:
    """Clear the registry. Test-only — never call this from application code."""
    _FACTOR_REGISTRY.clear()
