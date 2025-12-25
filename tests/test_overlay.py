import pandas as pd
import pytest

from scenarios.overlay_v2 import ScenarioParamsV2, apply_presets_v2, apply_scenario_v2
from scenarios.presets_v2 import PRESETS_V2


def _baseline(values, start="2026-11-01"):
    dates = pd.date_range(start, periods=len(values), freq="MS")
    return pd.DataFrame({"date": dates.date.astype(str), "yhat": values})


def test_growth_delta_adjusts_growth():
    baseline = _baseline([100.0, 110.0, 121.0])
    params = ScenarioParamsV2(growth_delta_pp_per_year=-0.24)
    result = apply_scenario_v2(baseline, params, "down")
    assert result["yhat"].iloc[0] == 100.0
    assert result["yhat"].iloc[1] == pytest.approx(108.0, rel=1e-6)
    assert result["yhat"].iloc[2] == pytest.approx(116.64, rel=1e-6)


def test_shock_year_applies_from_year_onward():
    baseline = _baseline([100.0, 110.0, 121.0], start="2026-12-01")
    params = ScenarioParamsV2(shock_start_year=2027, shock_pct=-0.1, shock_duration_months=0)
    result = apply_scenario_v2(baseline, params, "shock")
    assert result["yhat"].iloc[0] == 100.0
    assert result["yhat"].iloc[1] == pytest.approx(99.0, rel=1e-6)
    assert result["yhat"].iloc[2] < result["yhat"].iloc[1]


def test_shock_duration_temporary():
    baseline = _baseline([100.0, 110.0, 121.0, 133.1], start="2027-01-01")
    params = ScenarioParamsV2(shock_start_year=2027, shock_pct=-0.1, shock_duration_months=1)
    result = apply_scenario_v2(baseline, params, "shock")
    assert result["yhat"].iloc[1] < result["yhat"].iloc[2]


def test_drift_accumulates_over_time():
    baseline = _baseline([100.0, 100.0, 100.0, 100.0])
    params = ScenarioParamsV2(drift_pp_per_year=-0.12)
    result = apply_scenario_v2(baseline, params, "drift")
    assert result["yhat"].iloc[1] > result["yhat"].iloc[2]
    assert result["yhat"].iloc[2] > result["yhat"].iloc[3]


def test_non_negative_clipping():
    baseline = _baseline([100.0, 90.0], start="2027-01-01")
    params = ScenarioParamsV2(shock_start_year=2027, shock_pct=-1.5, shock_duration_months=0)
    result = apply_scenario_v2(baseline, params, "clip")
    assert (result["yhat"] >= 0).all()


def test_apply_presets_deterministic():
    baseline = _baseline([100.0, 110.0, 121.0])
    subset = {
        "base": PRESETS_V2["base"]["params"],
        "down": ScenarioParamsV2(growth_delta_pp_per_year=-0.12),
    }
    out1 = apply_presets_v2(baseline, subset)
    out2 = apply_presets_v2(baseline, subset)
    assert out1.equals(out2)
