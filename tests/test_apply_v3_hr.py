import pandas as pd
import pytest

from models.cost_fte import compute_alpha_beta
from scenarios.apply_v3 import apply_scenario_v3_hr
from scenarios.schema import ScenarioParamsV3


def _baseline_cost(values):
    dates = pd.date_range("2026-01-01", periods=len(values), freq="MS")
    return pd.DataFrame({"date": dates.date.astype(str), "yhat": values})


def test_beta_multiplier_scales_variable_component():
    baseline = _baseline_cost([10_000_000.0, 10_000_000.0])
    alpha, beta = compute_alpha_beta(10_000_000, 0.2, 800)
    params = ScenarioParamsV3(driver="cost", beta_multiplier=0.9)
    scenario = apply_scenario_v3_hr(baseline, params, alpha=alpha, beta=beta, scenario_name="beta_scale")
    # Variable part is 8M; 10% reduction -> expected 2M + 0.9*8M = 9.2M
    assert scenario["yhat"].iloc[0] == pytest.approx(9_200_000)


def test_cost_target_converts_to_fte_delta():
    baseline = _baseline_cost([10_000_000.0] * 6)
    alpha, beta = compute_alpha_beta(10_000_000, 0.2, 800)
    params = ScenarioParamsV3(driver="cost_target", cost_target_pct=-0.10)
    scenario = apply_scenario_v3_hr(baseline, params, alpha=alpha, beta=beta, scenario_name="cost_target")
    assert scenario["yhat"].iloc[0] == pytest.approx(9_000_000)
    assert (scenario["yhat"] >= 0).all()


def test_fte_driver_applies_delta_pct():
    baseline = _baseline_cost([10_000_000.0] * 3)
    alpha, beta = compute_alpha_beta(10_000_000, 0.2, 800)
    params = ScenarioParamsV3(driver="fte", fte_delta_pct=-0.1)
    scenario = apply_scenario_v3_hr(baseline, params, alpha=alpha, beta=beta, scenario_name="fte_cut")
    # Variable 8M reduced by 10% -> 2M + 7.2M = 9.2M
    assert scenario["yhat"].iloc[0] == pytest.approx(9_200_000)
