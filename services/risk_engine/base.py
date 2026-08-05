"""The RiskFactor base contract and RiskFactorResult type.

Kept separate from factors.py (concrete factors) and registry.py (the
registration mechanism) specifically to avoid a circular import: concrete
factors need `register_factor` from registry.py, and registry.py needs the
`RiskFactor` type — both can safely depend on this module without depending
on each other.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from models.asset import Asset
from models.exposure_signal import ExposureSignal


@dataclass(frozen=True)
class RiskFactorResult:
    """The outcome of evaluating one RiskFactor against one asset.

    Attributes:
        factor_name: The unique name of the factor that produced this result.
        weight_applied: Points contributed to the total score. Zero if the
            factor did not trigger.
        triggered: Whether this factor's condition was met at all.
        reason: Human-readable explanation, always populated (even when not
            triggered, e.g. "Asset is not flagged critical").
    """

    factor_name: str
    weight_applied: int
    triggered: bool
    reason: str


class RiskFactor(ABC):
    """Base contract every risk factor must implement.

    Attributes:
        name: Unique, stable identifier used in config (risk_weights.yaml)
            and in RiskFactorResult.factor_name. Renaming this is a breaking
            config change — treat it like an API contract.
        description: Human-readable explanation of what this factor checks,
            shown in documentation and audit output.
    """

    name: str
    description: str

    def __init__(self, weight: int) -> None:
        if weight < 0:
            raise ValueError(f"Factor weight must be non-negative, got {weight}.")
        self.weight = weight

    @abstractmethod
    def evaluate(self, asset: Asset, exposure_signals: list[ExposureSignal]) -> RiskFactorResult:
        """Evaluate this factor against a single asset and its signals.

        Must not raise for a "not triggered" case — always return a result;
        exceptions are reserved for genuinely invalid input.
        """
        raise NotImplementedError
