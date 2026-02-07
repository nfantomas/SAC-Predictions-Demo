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


def test_driver_resolution_backfill_phrase_keeps_positive_fte_direction():
    suggestion = {
        "scenario_driver": "auto",
        "suggested_driver": "fte",
        "params": {
            "driver": "fte",
            "lag_months": 6,
            "onset_duration_months": 3,
            "event_duration_months": 12,
            "recovery_duration_months": 3,
            "shape": "linear",
            "impact_mode": "level",
            "impact_magnitude": -0.2,
            "fte_delta_pct": -0.2,
            "growth_delta_pp_per_year": 0.0,
            "drift_pp_per_year": 0.0,
        },
    }
    ctx = build_driver_context(observed_t0_cost=10_000_000)
    user_text = "What happens if we introduce a 4-day workweek (reduced hours) in one region—what FTE backfill is required?"
    driver_used, params, warnings, derived, val_result = resolve_driver_and_params(
        suggestion,
        ctx,
        override_driver="auto",
        horizon_months=120,
        user_text=user_text,
    )
    assert driver_used == "fte"
    assert params.fte_delta_pct is not None and params.fte_delta_pct > 0
    assert params.impact_magnitude == 0.0
    assert isinstance(warnings, list)
    assert isinstance(derived, dict)
    assert hasattr(val_result, "errors")


def test_driver_resolution_keep_cost_flat_prefers_cost_target():
    suggestion = {
        "scenario_driver": "auto",
        "suggested_driver": "cost",
        "params": {
            "driver": "cost",
            "lag_months": 0,
            "onset_duration_months": 6,
            "event_duration_months": None,
            "recovery_duration_months": None,
            "shape": "linear",
            "impact_mode": "growth",
            "impact_magnitude": 0.0,
            "growth_delta_pp_per_year": 0.0,
            "drift_pp_per_year": 0.0,
            "cost_target_pct": None,
        },
    }
    ctx = build_driver_context(observed_t0_cost=10_000_000)
    user_text = "what will happen with FTEs if we want to keep costs at current level"
    driver_used, params, warnings, derived, val_result = resolve_driver_and_params(
        suggestion,
        ctx,
        override_driver="auto",
        horizon_months=120,
        user_text=user_text,
    )
    assert driver_used == "cost_target"
    assert params.cost_target_pct == 0.0
    assert isinstance(warnings, list)


def test_driver_resolution_explicit_fte_change_stays_fte():
    suggestion = {
        "scenario_driver": "auto",
        "suggested_driver": "cost_target",
        "params": {
            "driver": "cost_target",
            "lag_months": 0,
            "onset_duration_months": 0,
            "event_duration_months": None,
            "recovery_duration_months": None,
            "shape": "step",
            "impact_mode": "level",
            "impact_magnitude": 0.0,
            "growth_delta_pp_per_year": 0.0,
            "drift_pp_per_year": 0.0,
            "cost_target_pct": -0.1,
            "fte_delta_pct": None,
        },
    }
    ctx = build_driver_context(observed_t0_cost=10_000_000)
    user_text = "What will happen to costs if we reduce our workforce by 10%?"
    driver_used, params, warnings, derived, val_result = resolve_driver_and_params(
        suggestion,
        ctx,
        override_driver="auto",
        horizon_months=120,
        user_text=user_text,
    )
    assert driver_used == "fte"
    assert params.fte_delta_pct == -0.1
    assert params.cost_target_pct is None


def test_driver_resolution_aging_population_prefers_fte():
    suggestion = {
        "scenario_driver": "auto",
        "suggested_driver": "cost",
        "params": {
            "driver": "cost",
            "lag_months": 6,
            "onset_duration_months": 12,
            "shape": "linear",
            "impact_mode": "growth",
            "impact_magnitude": 0.0,
            "growth_delta_pp_per_year": 0.01,
            "drift_pp_per_year": 0.0,
        },
    }
    ctx = build_driver_context(observed_t0_cost=10_000_000)
    driver_used, params, warnings, _derived, _val_result = resolve_driver_and_params(
        suggestion,
        ctx,
        override_driver="auto",
        horizon_months=120,
        user_text="pressure from aging population and retirement pressure",
    )
    assert driver_used == "fte"


def test_driver_resolution_union_wage_hours_prefers_cost():
    suggestion = {
        "scenario_driver": "auto",
        "suggested_driver": "fte",
        "params": {
            "driver": "fte",
            "lag_months": 3,
            "onset_duration_months": 9,
            "shape": "linear",
            "impact_mode": "level",
            "impact_magnitude": 0.07,
            "fte_delta_pct": 0.05,
            "growth_delta_pp_per_year": 0.0,
            "drift_pp_per_year": 0.0,
        },
    }
    ctx = build_driver_context(observed_t0_cost=10_000_000)
    driver_used, params, warnings, _derived, _val_result = resolve_driver_and_params(
        suggestion,
        ctx,
        override_driver="auto",
        horizon_months=120,
        user_text="If union negotiations result in +7% wage increase plus reduced working hours, what is the combined impact?",
    )
    assert driver_used == "cost"


def test_driver_resolution_relocation_prefers_mix_shift_proxy():
    suggestion = {
        "scenario_driver": "auto",
        "suggested_driver": "fte",
        "params": {
            "driver": "fte",
            "lag_months": 0,
            "onset_duration_months": 0,
            "shape": "linear",
            "impact_mode": "level",
            "impact_magnitude": -0.02,
            "fte_delta_abs": -200,
            "growth_delta_pp_per_year": 0.0,
            "drift_pp_per_year": 0.0,
        },
    }
    ctx = build_driver_context(observed_t0_cost=10_000_000)
    driver_used, params, warnings, _derived, _val_result = resolve_driver_and_params(
        suggestion,
        ctx,
        override_driver="auto",
        horizon_months=120,
        user_text="What happens if we relocate 200 FTE from a high-cost country to a lower-cost country over 3 years?",
    )
    assert driver_used == "cost"
    assert params.beta_multiplier is not None and params.beta_multiplier < 1.0
    assert params.fte_delta_pct is None
    assert params.fte_delta_abs is None


def test_driver_resolution_downturn_stabilize_prefers_mix_shift_proxy():
    suggestion = {
        "scenario_driver": "auto",
        "suggested_driver": "fte",
        "params": {
            "driver": "fte",
            "lag_months": 0,
            "onset_duration_months": 0,
            "shape": "linear",
            "impact_mode": "level",
            "impact_magnitude": -0.05,
            "fte_delta_pct": -0.08,
            "growth_delta_pp_per_year": 0.0,
            "drift_pp_per_year": 0.0,
        },
    }
    ctx = build_driver_context(observed_t0_cost=10_000_000)
    driver_used, params, warnings, _derived, _val_result = resolve_driver_and_params(
        suggestion,
        ctx,
        override_driver="auto",
        horizon_months=120,
        user_text="If we simulate an economic downturn (revenue -10%, hiring slowdown, higher attrition), what is the recommended workforce plan to stabilize costs?",
    )
    assert driver_used == "cost"
    assert params.beta_multiplier is not None and params.beta_multiplier < 1.0
    assert params.fte_delta_pct is None
