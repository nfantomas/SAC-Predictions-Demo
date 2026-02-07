import pandas as pd

from llm.validate_v3 import ValidateContext, validate_and_sanitize_result


def test_cagr_out_of_bounds_warns_not_errors():
    params = {"lag_months": 0, "onset_duration_months": 0, "growth_delta_pp_per_year": 0.8}
    _, _, result = validate_and_sanitize_result(params, ctx=ValidateContext())
    assert result.errors == []
    assert result.warnings or result.clamps


def test_negative_cost_blocks():
    params = {"lag_months": 0, "onset_duration_months": 0}
    invalid_ctx = ValidateContext(alpha=10_500_000, beta=10_000, t0_cost=10_000_000)
    _, _, result = validate_and_sanitize_result(params, ctx=invalid_ctx)
    assert result.errors


def test_multiplier_out_of_bounds_warns():
    params = {"lag_months": 0, "onset_duration_months": 0, "impact_mode": "level", "impact_magnitude": 0.5}
    tight_ctx = ValidateContext(multiplier_max=0.5, multiplier_min=0.9)
    _, _, result = validate_and_sanitize_result(params, ctx=tight_ctx)
    assert result.errors == []
    all_msgs = [w.message for w in result.warnings] + [c.message for c in result.clamps]
    assert all_msgs
