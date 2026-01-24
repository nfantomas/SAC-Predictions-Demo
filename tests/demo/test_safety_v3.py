import pandas as pd

from demo.llm.safety_v3 import SafetyBounds, validate_sanity_v3
from scenarios.schema import ScenarioParamsV3


def _baseline(cost: float = 10_000_000, months: int = 120) -> pd.DataFrame:
    dates = pd.date_range("2028-01-01", periods=months, freq="MS")
    return pd.DataFrame({"date": dates, "yhat": [cost] * months})


def test_validate_sanity_v3_within_bounds():
    params = ScenarioParamsV3(
        driver="cost",
        lag_months=6,
        onset_duration_months=3,
        event_duration_months=6,
        recovery_duration_months=None,
        shape="step",
        impact_mode="level",
        impact_magnitude=-0.05,
        growth_delta_pp_per_year=0.0,
        drift_pp_per_year=0.0,
        event_growth_delta_pp_per_year=None,
        event_growth_exp_multiplier=None,
        post_event_growth_pp_per_year=None,
        fte_delta_abs=None,
        fte_delta_pct=None,
        beta_multiplier=None,
        cost_target_pct=None,
    )
    ok, warnings, blocks = validate_sanity_v3(params, _baseline(), SafetyBounds())
    assert ok
    assert not blocks


def test_validate_sanity_v3_blocks_extreme_multiplier():
    params = ScenarioParamsV3(
        driver="cost",
        lag_months=0,
        onset_duration_months=0,
        event_duration_months=0,
        recovery_duration_months=None,
        shape="step",
        impact_mode="level",
        impact_magnitude=5.0,  # extreme
        growth_delta_pp_per_year=0.0,
        drift_pp_per_year=0.0,
        event_growth_delta_pp_per_year=None,
        event_growth_exp_multiplier=None,
        post_event_growth_pp_per_year=None,
        fte_delta_abs=None,
        fte_delta_pct=None,
        beta_multiplier=None,
        cost_target_pct=None,
    )
    ok, warnings, blocks = validate_sanity_v3(params, _baseline(), SafetyBounds(max_multiplier=2.0, extreme_max_multiplier=3.0))
    assert not ok
    assert blocks


def test_validate_sanity_v3_warns_on_jump():
    params = ScenarioParamsV3(
        driver="cost",
        lag_months=0,
        onset_duration_months=0,
        event_duration_months=None,
        recovery_duration_months=None,
        shape="step",
        impact_mode="level",
        impact_magnitude=0.0,
        growth_delta_pp_per_year=0.0,
        drift_pp_per_year=0.0,
        event_growth_delta_pp_per_year=None,
        event_growth_exp_multiplier=None,
        post_event_growth_pp_per_year=None,
        fte_delta_abs=None,
        fte_delta_pct=None,
        beta_multiplier=None,
        cost_target_pct=None,
    )
    # Modify baseline to force a big jump after apply
    baseline = _baseline()
    baseline.loc[0, "yhat"] = 1_000
    ok, warnings, blocks = validate_sanity_v3(params, baseline, SafetyBounds(max_monthly_jump_pct=0.1))
    assert ok
    assert any("jump" in w.lower() for w in warnings)
