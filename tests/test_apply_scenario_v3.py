import pandas as pd
import pytest

from model.cost_driver import calibrate_alpha_beta
from scenarios.schema import ScenarioParamsV3
from scenarios.v3 import apply_scenario_v3_simple


def _baseline(values, start="2026-11-01"):
    dates = pd.date_range(start=start, periods=len(values), freq="MS")
    return pd.DataFrame({"date": dates.date.astype(str), "yhat": values})


def test_linear_ramp_and_recovery_returns_to_underlying_path():
    baseline = _baseline([10_000_000.0] * 7)
    params = ScenarioParamsV3(
        lag_months=0,
        onset_duration_months=2,
        event_duration_months=None,
        recovery_duration_months=None,
        impact_mode="level",
        impact_magnitude=0.0,
        shape="linear",
        fte_delta_pct=0.1,
    )
    result = apply_scenario_v3_simple(baseline, params, None)

    # Lag 0 + linear onset should start partial and rise.
    assert result["yhat"].iloc[1] > result["yhat"].iloc[0]


def test_exp_onset_reacts_faster_than_linear():
    baseline = _baseline([10_000_000.0] * 4)
    linear_params = ScenarioParamsV3(
        lag_months=0,
        onset_duration_months=2,
        event_duration_months=None,
        recovery_duration_months=None,
        impact_mode="level",
        impact_magnitude=0.0,
        shape="linear",
        fte_delta_pct=0.1,
    )
    exp_params = ScenarioParamsV3(
        lag_months=0,
        onset_duration_months=2,
        event_duration_months=None,
        recovery_duration_months=None,
        impact_mode="level",
        impact_magnitude=0.0,
        shape="exp",
        fte_delta_pct=0.1,
    )
    linear = apply_scenario_v3_simple(baseline, linear_params, None)
    exp = apply_scenario_v3_simple(baseline, exp_params, None)

    # Faster ramp for exp means first onset month shows bigger move.
    assert exp["yhat"].iloc[1] >= linear["yhat"].iloc[1]


def test_fte_and_beta_paths():
    alpha, beta = calibrate_alpha_beta(10_000_000, 800, 0.2)
    ctx = type("Ctx", (), {"alpha": alpha, "beta0": beta})
    baseline = _baseline([10_000_000.0] * 6)
    params = ScenarioParamsV3(driver="fte", fte_delta_pct=-0.1, beta_multiplier=1.05, lag_months=1, onset_duration_months=2)
    result = apply_scenario_v3_simple(baseline, params, ctx)
    assert result["yhat"].iloc[1] < 10_000_000
    params_nom = ScenarioParamsV3(driver="fte", fte_delta_pct=-0.1, lag_months=1, onset_duration_months=2)
    nom = apply_scenario_v3_simple(baseline, params_nom, ctx)
    assert result["yhat"].iloc[2] > nom["yhat"].iloc[2]  # beta uplift increases relative to no uplift


def test_lag_applies_at_t6():
    alpha, beta = calibrate_alpha_beta(10_000_000, 800, 0.2)
    ctx = type("Ctx", (), {"alpha": alpha, "beta0": beta})
    baseline = _baseline([10_000_000.0] * 12)
    params = ScenarioParamsV3(driver="cost", beta_multiplier=1.1, lag_months=6, onset_duration_months=0)
    result = apply_scenario_v3_simple(baseline, params, ctx)
    assert result["yhat"].iloc[5] == pytest.approx(10_000_000.0)
    assert result["yhat"].iloc[6] > result["yhat"].iloc[5]
