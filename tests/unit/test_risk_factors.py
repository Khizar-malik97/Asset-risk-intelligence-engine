"""Unit tests for the risk factor framework: base contract, registry, weight
config loading, and each concrete factor's evaluation logic."""

from pathlib import Path
from uuid import UUID

import pytest

from models.asset import Asset
from models.exposure_signal import ExposureSeverity, ExposureSignal, ExposureSignalType
from models.host import Host
from models.user import User
from services.risk_engine.base import RiskFactor, RiskFactorResult
from services.risk_engine.factors import (
    CriticalAssetFactor,
    InternetFacingFactor,
    PrivilegedAccountFactor,
    UnpatchedVulnerabilityFactor,
)
from services.risk_engine.registry import (
    clear_registry,
    get_registered_factors,
    register_factor,
)
from services.risk_engine.weights import RiskWeightConfigError, build_factors, load_risk_weights


def _signal(signal_type: ExposureSignalType, asset_id: UUID) -> ExposureSignal:
    return ExposureSignal(
        asset_id=asset_id,
        signal_type=signal_type,
        severity=ExposureSeverity.HIGH,
        description="test signal",
    )


def _reset_registry_to_real_factors() -> None:
    """Wipe the registry completely, then reload factors.py so only the
    real, decorated factors are registered again — used to clean up after
    tests that deliberately register temporary/broken factors, so those
    don't leak into later tests (e.g. the one that checks the real config
    file against the real registry)."""
    import importlib

    import services.risk_engine.factors as factors_module

    clear_registry()
    importlib.reload(factors_module)


class TestRiskFactorBase:
    def test_negative_weight_rejected(self) -> None:
        with pytest.raises(ValueError):
            CriticalAssetFactor(weight=-5)

    def test_zero_weight_allowed(self) -> None:
        # A factor with weight 0 is a valid (if pointless) config state —
        # should not raise.
        factor = CriticalAssetFactor(weight=0)
        assert factor.weight == 0


class TestRegistry:
    def test_real_factors_are_registered_on_import(self) -> None:
        # Importing services.risk_engine.factors (done at module load above)
        # must have registered all four concrete factors via the decorator.
        registered = get_registered_factors()

        assert "critical_asset_flag" in registered
        assert "internet_facing" in registered
        assert "unpatched_vulnerability" in registered
        assert "privileged_account" in registered

    def test_register_factor_requires_a_name(self) -> None:
        clear_registry()
        try:
            with pytest.raises(ValueError):

                @register_factor
                class NoNameFactor(RiskFactor):
                    def evaluate(
                        self, asset: Asset, exposure_signals: list[ExposureSignal]
                    ) -> RiskFactorResult:
                        return RiskFactorResult(
                            factor_name="unused", weight_applied=0, triggered=False, reason=""
                        )

        finally:
            _reset_registry_to_real_factors()

    def test_duplicate_name_rejected(self) -> None:
        clear_registry()
        try:

            @register_factor
            class FirstFactor(RiskFactor):
                name = "duplicate_name"
                description = "first"

                def evaluate(
                    self, asset: Asset, exposure_signals: list[ExposureSignal]
                ) -> RiskFactorResult:
                    return RiskFactorResult(
                        factor_name=self.name, weight_applied=0, triggered=False, reason=""
                    )

            with pytest.raises(ValueError):

                @register_factor
                class SecondFactor(RiskFactor):
                    name = "duplicate_name"
                    description = "second"

                    def evaluate(
                        self, asset: Asset, exposure_signals: list[ExposureSignal]
                    ) -> RiskFactorResult:
                        return RiskFactorResult(
                            factor_name=self.name, weight_applied=0, triggered=False, reason=""
                        )

        finally:
            _reset_registry_to_real_factors()


class TestLoadRiskWeights:
    def test_load_valid_weights(self, tmp_path: Path) -> None:
        config_file = tmp_path / "risk_weights.yaml"
        config_file.write_text("critical_asset_flag: 30\ninternet_facing: 25\n")

        weights = load_risk_weights(config_file)

        assert weights == {"critical_asset_flag": 30, "internet_facing": 25}

    def test_missing_file_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(RiskWeightConfigError):
            load_risk_weights(tmp_path / "does_not_exist.yaml")

    def test_empty_file_rejected(self, tmp_path: Path) -> None:
        config_file = tmp_path / "risk_weights.yaml"
        config_file.write_text("")

        with pytest.raises(RiskWeightConfigError):
            load_risk_weights(config_file)

    def test_negative_weight_rejected(self, tmp_path: Path) -> None:
        config_file = tmp_path / "risk_weights.yaml"
        config_file.write_text("critical_asset_flag: -10\n")

        with pytest.raises(RiskWeightConfigError):
            load_risk_weights(config_file)

    def test_non_integer_weight_rejected(self, tmp_path: Path) -> None:
        config_file = tmp_path / "risk_weights.yaml"
        config_file.write_text("critical_asset_flag: not_a_number\n")

        with pytest.raises(RiskWeightConfigError):
            load_risk_weights(config_file)

    def test_non_mapping_content_rejected(self, tmp_path: Path) -> None:
        config_file = tmp_path / "risk_weights.yaml"
        config_file.write_text("- just\n- a\n- list\n")

        with pytest.raises(RiskWeightConfigError):
            load_risk_weights(config_file)


class TestBuildFactors:
    def test_builds_one_instance_per_registered_factor(self) -> None:
        registry: dict[str, type[RiskFactor]] = {"critical_asset_flag": CriticalAssetFactor}
        weights = {"critical_asset_flag": 30}

        factors = build_factors(weights, registry=registry)

        assert len(factors) == 1
        assert factors[0].weight == 30

    def test_missing_weight_for_registered_factor_rejected(self) -> None:
        registry: dict[str, type[RiskFactor]] = {"critical_asset_flag": CriticalAssetFactor}
        weights: dict[str, int] = {}

        with pytest.raises(RiskWeightConfigError):
            build_factors(weights, registry=registry)

    def test_unknown_weight_key_rejected(self) -> None:
        registry: dict[str, type[RiskFactor]] = {"critical_asset_flag": CriticalAssetFactor}
        weights = {"critical_asset_flag": 30, "made_up_factor": 10}

        with pytest.raises(RiskWeightConfigError):
            build_factors(weights, registry=registry)

    def test_real_config_file_matches_real_registry(self) -> None:
        """The actual config/risk_weights.yaml must have exactly one entry
        per real registered factor — this is the integration point between
        the two halves of the framework."""
        weights = load_risk_weights("config/risk_weights.yaml")
        factors = build_factors(weights)

        assert len(factors) == len(get_registered_factors())


class TestCriticalAssetFactor:
    def test_triggers_for_critical_asset(self) -> None:
        factor = CriticalAssetFactor(weight=30)
        asset = Host(identifier="web-01", is_critical=True)

        result = factor.evaluate(asset, [])

        assert result.triggered is True
        assert result.weight_applied == 30

    def test_does_not_trigger_for_non_critical_asset(self) -> None:
        factor = CriticalAssetFactor(weight=30)
        asset = Host(identifier="web-02", is_critical=False)

        result = factor.evaluate(asset, [])

        assert result.triggered is False
        assert result.weight_applied == 0


class TestInternetFacingFactor:
    def test_triggers_when_signal_present(self) -> None:
        factor = InternetFacingFactor(weight=25)
        asset = Host(identifier="web-03")
        signal = _signal(ExposureSignalType.INTERNET_FACING, asset.id)

        result = factor.evaluate(asset, [signal])

        assert result.triggered is True
        assert result.weight_applied == 25

    def test_does_not_trigger_without_signal(self) -> None:
        factor = InternetFacingFactor(weight=25)
        asset = Host(identifier="web-04")

        result = factor.evaluate(asset, [])

        assert result.triggered is False
        assert result.weight_applied == 0

    def test_ignores_unrelated_signal_types(self) -> None:
        factor = InternetFacingFactor(weight=25)
        asset = Host(identifier="web-05")
        signal = _signal(ExposureSignalType.WEAK_AUTHENTICATION, asset.id)

        result = factor.evaluate(asset, [signal])

        assert result.triggered is False


class TestUnpatchedVulnerabilityFactor:
    def test_no_trigger_with_zero_signals(self) -> None:
        factor = UnpatchedVulnerabilityFactor(weight=15)
        asset = Host(identifier="web-06")

        result = factor.evaluate(asset, [])

        assert result.triggered is False
        assert result.weight_applied == 0

    def test_single_signal_contributes_full_weight(self) -> None:
        factor = UnpatchedVulnerabilityFactor(weight=15)
        asset = Host(identifier="web-07")
        signal = _signal(ExposureSignalType.UNPATCHED_VULNERABILITY, asset.id)

        result = factor.evaluate(asset, [signal])

        assert result.triggered is True
        assert result.weight_applied == 15

    def test_multiple_signals_scale_contribution(self) -> None:
        factor = UnpatchedVulnerabilityFactor(weight=15)
        asset = Host(identifier="web-08")
        signals = [_signal(ExposureSignalType.UNPATCHED_VULNERABILITY, asset.id) for _ in range(2)]

        result = factor.evaluate(asset, signals)

        assert result.weight_applied == 30

    def test_contribution_caps_at_three_signals(self) -> None:
        factor = UnpatchedVulnerabilityFactor(weight=15)
        asset = Host(identifier="web-09")
        signals = [_signal(ExposureSignalType.UNPATCHED_VULNERABILITY, asset.id) for _ in range(10)]

        result = factor.evaluate(asset, signals)

        assert result.weight_applied == 45  # 15 * 3, capped
        assert "capped" in result.reason


class TestPrivilegedAccountFactor:
    def test_triggers_for_privileged_user(self) -> None:
        factor = PrivilegedAccountFactor(weight=20)
        user = User(identifier="admin_jdoe", is_privileged=True)

        result = factor.evaluate(user, [])

        assert result.triggered is True
        assert result.weight_applied == 20

    def test_does_not_trigger_for_non_privileged_user(self) -> None:
        factor = PrivilegedAccountFactor(weight=20)
        user = User(identifier="jdoe", is_privileged=False)

        result = factor.evaluate(user, [])

        assert result.triggered is False

    def test_does_not_trigger_for_privileged_host(self) -> None:
        """A Host has no is_privileged attribute at all — the factor must
        handle that gracefully (not crash) and simply not trigger."""
        factor = PrivilegedAccountFactor(weight=20)
        host = Host(identifier="web-10")

        result = factor.evaluate(host, [])

        assert result.triggered is False
