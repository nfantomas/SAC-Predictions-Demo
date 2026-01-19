import pytest

from llm.validate_suggestion import SuggestionValidationError, validate_suggestion


def test_extreme_growth_clamped_or_rejected():
    params = {
        "lag_months": 0,
        "onset_duration_months": 0,
        "event_duration_months": None,
        "recovery_duration_months": None,
        "shape": "step",
        "impact_mode": "growth",
        "impact_magnitude": 0.6,  # above bound, should clamp
        "growth_delta_pp_per_year": 0.6,
        "drift_pp_per_year": 0.4,
    }
    validated, warnings = validate_suggestion(params)
    assert warnings  # clamped
    assert validated.impact_magnitude <= 0.5
    assert validated.growth_delta_pp_per_year <= 0.5


def test_safe_params_pass():
    params = {
        "lag_months": 1,
        "onset_duration_months": 3,
        "event_duration_months": 6,
        "recovery_duration_months": 6,
        "shape": "linear",
        "impact_mode": "level",
        "impact_magnitude": 0.05,
        "growth_delta_pp_per_year": 0.05,
        "drift_pp_per_year": 0.02,
    }
    validated, warnings = validate_suggestion(params)
    assert isinstance(warnings, list)
    assert validated.lag_months == 1


def test_extreme_negative_rejected_after_clamp():
    params = {
        "lag_months": 0,
        "onset_duration_months": 0,
        "event_duration_months": None,
        "recovery_duration_months": None,
        "shape": "step",
        "impact_mode": "level",
        "impact_magnitude": -0.9,
        "growth_delta_pp_per_year": -0.5,
        "drift_pp_per_year": -0.3,
    }
    validated, warnings = validate_suggestion(params)
    assert warnings
    assert validated.impact_magnitude >= -0.5
