import pandas as pd
import pytest

from llm.validate_v3 import ValidateContext, validate_and_sanitize_result


def test_clamps_extreme_growth_and_returns_warnings():
    params = {
        "lag_months": 0,
        "onset_duration_months": 0,
        "impact_mode": "level",
        "impact_magnitude": 1.5,
        "growth_delta_pp_per_year": 1.0,
    }
    validated, warnings, result = validate_and_sanitize_result(params, ctx=ValidateContext())
    assert warnings or result.warnings
    assert validated.impact_magnitude <= 1.0
    assert validated.growth_delta_pp_per_year <= 0.5


def test_multiplier_out_of_bounds_warns_after_clamp():
    params = {
        "lag_months": 0,
        "onset_duration_months": 0,
        "impact_mode": "level",
        "impact_magnitude": 0.8,
    }
    tight_ctx = ValidateContext(multiplier_max=0.5, multiplier_min=0.9)
    _, _, result = validate_and_sanitize_result(params, ctx=tight_ctx)
    assert result.errors == []
    assert result.warnings


def test_invalid_lag_rejected():
    params = {
        "lag_months": -1,
        "onset_duration_months": 0,
        "impact_mode": "level",
        "impact_magnitude": 0.1,
    }
    _, _, result = validate_and_sanitize_result(params, ctx=ValidateContext(horizon_months=12))
    assert result.errors
