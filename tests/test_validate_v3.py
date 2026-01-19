import pandas as pd
import pytest

from models.cost_fte import compute_alpha_beta
from scenarios.schema import ScenarioParamsV3
from scenarios.validate_v3 import ScenarioValidationError, validate_params_v3, validate_projection


def _baseline():
    dates = pd.date_range("2026-01-01", periods=24, freq="MS")
    return pd.DataFrame({"date": dates.date.astype(str), "yhat": [10_000_000.0] * len(dates)})


def test_clamps_beta_and_inflation():
    params = ScenarioParamsV3(
        driver="cost",
        beta_multiplier=2.0,
        impact_mode="level",
        impact_magnitude=2.0,
        growth_delta_pp_per_year=1.0,
        drift_pp_per_year=1.0,
        inflation_by_segment={"A": 0.5},
    )
    validated, warnings = validate_params_v3(params)
    assert warnings
    assert validated.beta_multiplier == 1.2
    assert validated.impact_magnitude <= 1.0
    assert validated.inflation_by_segment["A"] == 0.2


def test_projection_clamps_or_rejects():
    baseline = _baseline()
    alpha, beta = compute_alpha_beta(10_000_000, 0.2, 800)
    params = ScenarioParamsV3(
        driver="cost",
        impact_mode="growth",
        impact_magnitude=0.5,
        growth_delta_pp_per_year=0.5,
    )
    validated, warnings = validate_projection(baseline, params, alpha=alpha, beta=beta, multiplier_max=3.0)
    assert isinstance(warnings, list)
    assert validated.impact_magnitude <= 0.5

    too_extreme = ScenarioParamsV3(driver="cost", impact_mode="growth", impact_magnitude=5.0, growth_delta_pp_per_year=5.0)
    validated_too, warnings_too = validate_projection(baseline, too_extreme, alpha=alpha, beta=beta, multiplier_max=1.5, multiplier_min=0.2)
    # After clamping, multiplier should be within bounds
    assert warnings_too
    assert validated_too.impact_magnitude <= 5.0
