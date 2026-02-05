import json
from pathlib import Path

import pandas as pd

from model.cost_driver import calibrate_alpha_beta
from scenarios.overlay_v2 import ScenarioParamsV2, apply_scenario_v2
from scenarios.presets_v2 import PRESETS_V2
from scenarios.presets_v3 import PRESETS_V3
from scenarios.v3 import DriverContext as V3DriverContext, apply_scenario_v3_simple
from ui.assistant_v3_pipeline import build_driver_context, resolve_driver_and_params


def _baseline_df(months: int = 24, start: float = 10_000_000, growth_ppm: float = 0.01) -> pd.DataFrame:
    dates = pd.date_range("2028-01-01", periods=months, freq="MS")
    values = [start * ((1 + growth_ppm) ** i) for i in range(months)]
    return pd.DataFrame({"date": dates, "yhat": values})


def test_v2_apply_smoke():
    assert PRESETS_V2, "V2 presets should not be empty"
    baseline = _baseline_df(months=36)
    params = ScenarioParamsV2(growth_delta_pp_per_year=-0.02, shock_start_year=2029, shock_pct=-0.05, shock_duration_months=6)
    out = apply_scenario_v2(baseline, params, scenario_name="test_v2")
    assert not out.empty
    assert len(out) == len(baseline)


def test_v3_apply_smoke():
    assert PRESETS_V3, "V3 presets should not be empty"
    baseline = _baseline_df(months=60)
    alpha, beta0 = calibrate_alpha_beta(10_000_000, 800, 0.2)
    ctx = V3DriverContext(alpha=alpha, beta0=beta0)
    first_preset = next(iter(PRESETS_V3.values()))
    out = apply_scenario_v3_simple(baseline, first_preset.params, context=ctx, horizon_months=len(baseline))
    assert not out.empty
    assert len(out) == len(baseline)


def test_driver_resolution_with_fixture():
    fixture = json.loads(Path("demo/llm/fixtures/reduce_costs_10pct.json").read_text())
    ctx = build_driver_context(observed_t0_cost=10_000_000)
    driver_used, params, warnings, derived, val_result = resolve_driver_and_params(fixture, ctx, override_driver="auto", horizon_months=120)
    assert driver_used == "cost_target"
    assert params.cost_target_pct is not None
    assert isinstance(warnings, list)
    assert isinstance(derived, dict)
    assert hasattr(val_result, "errors")
