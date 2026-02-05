import pandas as pd

from config.core import BASELINE_GROWTH_YOY
from llm.validate_v3 import ValidateContext, validate_and_sanitize_result
from scenarios.schema import ScenarioParamsV3
from scenarios.v3 import DriverContext, apply_scenario_v3_simple


def _baseline(cost: float = 10_000_000, months: int = 120) -> pd.DataFrame:
    dates = pd.date_range("2028-01-01", periods=months, freq="MS")
    return pd.DataFrame({"date": dates, "yhat": [cost] * months})


def test_flat_cost_intent_allows_scenario():
    # Hold costs roughly flat by canceling baseline growth
    params = ScenarioParamsV3(
        driver="cost",
        lag_months=0,
        onset_duration_months=0,
        impact_mode="growth",
        growth_delta_pp_per_year=-BASELINE_GROWTH_YOY,
    )
    _, warnings, result = validate_and_sanitize_result(params.__dict__, ctx=ValidateContext(horizon_months=120))
    assert not result.errors
    # Apply to ensure it runs
    ctx = DriverContext(alpha=0.2, beta0=0.001)
    scenario = apply_scenario_v3_simple(_baseline(), params, context=ctx)
    assert not scenario.empty


def test_macro_shock_visible_but_within_bounds():
    params = ScenarioParamsV3(
        driver="cost",
        lag_months=12,
        onset_duration_months=3,
        impact_mode="level",
        impact_magnitude=-0.2,
        recovery_duration_months=6,
    )
    _, warnings, result = validate_and_sanitize_result(params.__dict__, ctx=ValidateContext(horizon_months=120))
    assert not result.errors
    ctx = DriverContext(alpha=0.2, beta0=0.001)
    scenario = apply_scenario_v3_simple(_baseline(), params, context=ctx)
    assert not scenario.empty
