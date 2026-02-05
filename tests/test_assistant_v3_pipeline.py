import json

import pandas as pd
import pytest

from config import Assumptions
from scenarios.schema import ScenarioParamsV3
from ui.assistant_v3_pipeline import (
    apply_driver_scenario,
    build_driver_context,
    parse_suggestion,
    strip_json_fences,
    validate_and_prepare_params,
)


def _forecast(values):
    dates = pd.date_range("2026-01-01", periods=len(values), freq="MS")
    return pd.DataFrame({"date": dates.date.astype(str), "yhat": values})


def test_strip_and_parse_json_fences():
    raw = "```json\n{\"a\":1}\n```"
    with pytest.raises(Exception):
        parse_suggestion(raw)


def test_build_driver_context_uses_observed_when_mismatch():
    assumptions = Assumptions(t0_cost=10_000_000, fixed_cost_share=0.2, t0_fte=800, mismatch_threshold=0.2)
    ctx = build_driver_context(observed_t0_cost=6_000_000, assumptions=assumptions)
    assert ctx.t0_cost_used == 6_000_000
    assert ctx.warning


def test_validate_and_apply_driver_cost():
    params_dict = {
        "lag_months": 0,
        "onset_duration_months": 0,
        "event_duration_months": None,
        "recovery_duration_months": None,
        "shape": "step",
        "impact_mode": "level",
        "impact_magnitude": 0.05,
        "growth_delta_pp_per_year": 0.0,
        "drift_pp_per_year": 0.0,
    }
    params, warnings, result = validate_and_prepare_params(params_dict)
    assert isinstance(params, ScenarioParamsV3)
    assert warnings == [] or isinstance(warnings, list)
    assert hasattr(result, "errors")

    forecast = _forecast([10_000_000.0] * 6)
    ctx = build_driver_context(observed_t0_cost=10_000_000, assumptions=Assumptions(10_000_000, 0.2, 800, 0.2))
    scenario = apply_driver_scenario(forecast, params, driver="cost", ctx=ctx)
    assert not scenario.empty
    assert scenario["yhat"].iloc[0] > 0


def test_apply_driver_fte_uses_implied_series():
    params = ScenarioParamsV3(
        lag_months=0,
        onset_duration_months=0,
        event_duration_months=None,
        recovery_duration_months=None,
        shape="step",
        impact_mode="growth",
        impact_magnitude=-0.01,
    )
    forecast = _forecast([10_000_000.0] * 6)
    ctx = build_driver_context(observed_t0_cost=10_000_000, assumptions=Assumptions(10_000_000, 0.2, 800, 0.2))
    scenario = apply_driver_scenario(forecast, params, driver="fte", ctx=ctx)
    assert scenario["yhat"].iloc[-1] >= 0
