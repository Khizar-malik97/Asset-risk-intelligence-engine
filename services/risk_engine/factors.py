"""Concrete risk factors.

Each factor evaluates one specific, named signal about an asset (e.g. "is
this asset flagged critical?") and returns a RiskFactorResult carrying both
a numeric contribution and a human-readable reason. The Scoring Engine
(Milestone 13) sums these results — this module only defines what each
individual factor checks, never how they combine.

Every factor must be explainable: no factor may consult anything outside
the asset and its exposure signals, and every result must include a reason
string, per NFR-1 (explainability/reproducibility).

Every factor class below is decorated with @register_factor, which adds it
to the global registry purely by being imported — see registry.py.
"""

from models.asset import Asset
from models.enums import AssetType
from models.exposure_signal import ExposureSignal, ExposureSignalType
from services.risk_engine.base import RiskFactor, RiskFactorResult
from services.risk_engine.registry import register_factor


@register_factor
class CriticalAssetFactor(RiskFactor):
    """Contributes full weight if the asset is flagged business-critical."""

    name = "critical_asset_flag"
    description = "Asset has been manually flagged as business-critical."

    def evaluate(self, asset: Asset, exposure_signals: list[ExposureSignal]) -> RiskFactorResult:
        if asset.is_critical:
            return RiskFactorResult(
                factor_name=self.name,
                weight_applied=self.weight,
                triggered=True,
                reason="Asset is flagged as business-critical.",
            )
        return RiskFactorResult(
            factor_name=self.name,
            weight_applied=0,
            triggered=False,
            reason="Asset is not flagged as critical.",
        )


@register_factor
class InternetFacingFactor(RiskFactor):
    """Contributes full weight if any exposure signal marks the asset as
    internet-facing."""

    name = "internet_facing"
    description = "Asset has an exposure signal indicating internet-facing exposure."

    def evaluate(self, asset: Asset, exposure_signals: list[ExposureSignal]) -> RiskFactorResult:
        has_signal = any(
            signal.signal_type == ExposureSignalType.INTERNET_FACING for signal in exposure_signals
        )
        if has_signal:
            return RiskFactorResult(
                factor_name=self.name,
                weight_applied=self.weight,
                triggered=True,
                reason="Asset has an internet-facing exposure signal.",
            )
        return RiskFactorResult(
            factor_name=self.name,
            weight_applied=0,
            triggered=False,
            reason="No internet-facing exposure signal present.",
        )


@register_factor
class UnpatchedVulnerabilityFactor(RiskFactor):
    """Contributes weight per unpatched-vulnerability signal, capped at 3
    signals worth, so a single asset with dozens of CVEs doesn't dominate
    the score disproportionately."""

    name = "unpatched_vulnerability"
    description = (
        "Asset has one or more unpatched-vulnerability exposure signals "
        "(contribution capped at 3 signals)."
    )
    _MAX_COUNTED_SIGNALS = 3

    def evaluate(self, asset: Asset, exposure_signals: list[ExposureSignal]) -> RiskFactorResult:
        matching = [
            s
            for s in exposure_signals
            if s.signal_type == ExposureSignalType.UNPATCHED_VULNERABILITY
        ]
        count = len(matching)
        if count == 0:
            return RiskFactorResult(
                factor_name=self.name,
                weight_applied=0,
                triggered=False,
                reason="No unpatched-vulnerability signals present.",
            )

        counted = min(count, self._MAX_COUNTED_SIGNALS)
        contribution = self.weight * counted
        reason = f"{count} unpatched-vulnerability signal(s) present"
        if count > self._MAX_COUNTED_SIGNALS:
            reason += f" (capped at {self._MAX_COUNTED_SIGNALS} for scoring)"
        return RiskFactorResult(
            factor_name=self.name,
            weight_applied=contribution,
            triggered=True,
            reason=reason + ".",
        )


@register_factor
class PrivilegedAccountFactor(RiskFactor):
    """Contributes full weight if the asset is a User account flagged
    privileged. Always non-triggered for non-User assets."""

    name = "privileged_account"
    description = "Asset is a user account with elevated/administrative privileges."

    def evaluate(self, asset: Asset, exposure_signals: list[ExposureSignal]) -> RiskFactorResult:
        is_privileged_user = asset.asset_type == AssetType.USER and getattr(
            asset, "is_privileged", False
        )
        if is_privileged_user:
            return RiskFactorResult(
                factor_name=self.name,
                weight_applied=self.weight,
                triggered=True,
                reason="Asset is a privileged user account.",
            )
        return RiskFactorResult(
            factor_name=self.name,
            weight_applied=0,
            triggered=False,
            reason="Asset is not a privileged user account.",
        )
