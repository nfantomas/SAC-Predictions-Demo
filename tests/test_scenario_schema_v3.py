import pandas as pd
import pytest

from scenarios.overlay_v2 import ScenarioParamsV2
from scenarios.schema import ScenarioParamsV3, migrate_params_v2_to_v3


def _baseline(start="2026-11-01", periods=6):
    dates = pd.date_range(start=start, periods=periods, freq="MS")
    return pd.DataFrame({"date": dates.date.astype(str), "yhat": [100.0] * periods})


def test_v3_validation_rejects_invalid_values():
    with pytest.raises(ValueError):
        ScenarioParamsV3(onset_duration_months=-1)
    with pytest.raises(ValueError):
        ScenarioParamsV3(shape="bad")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        ScenarioParamsV3(impact_mode="weird")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        ScenarioParamsV3(recovery_duration_months=-2)
    with pytest.raises(ValueError):
        ScenarioParamsV3(beta_multiplier=0)


def test_migrate_v2_to_v3_maps_shock_and_growth_fields():
    baseline = _baseline()
    params = ScenarioParamsV2(
        growth_delta_pp_per_year=-0.12,
        shock_start_year=2027,
        shock_pct=-0.1,
        shock_duration_months=6,
        drift_pp_per_year=0.02,
    )
    migrated = migrate_params_v2_to_v3(baseline, params)
    assert migrated.lag_months == 2  # 2026-11 -> 2027-01 is index 2
    assert migrated.impact_magnitude == -0.1
    assert migrated.event_duration_months == 6
    assert migrated.recovery_duration_months == 0
    assert migrated.growth_delta_pp_per_year == -0.12
    assert migrated.drift_pp_per_year == 0.02


def test_migrate_v2_to_v3_ignores_missing_shock_year():
    baseline = _baseline()
    params = ScenarioParamsV2(shock_start_year=2040, shock_pct=-0.2)
    migrated = migrate_params_v2_to_v3(baseline, params)
    assert migrated.lag_months == 0
    assert migrated.impact_magnitude == 0.0


def test_new_fields_accept_defaults():
    params = ScenarioParamsV3(
        driver="cost_target",
        beta_multiplier=0.95,
        fte_delta_abs=-120,
        fte_delta_pct=-0.15,
        cost_target_pct=-0.1,
        inflation_by_segment={"A": 0.05, "B": 0.08},
        segment_weights={"A": 0.6, "B": 0.4},
        fte_cut_plan={"Junior": 50, "Senior": 10},
    )
    assert params.driver == "cost_target"
    assert params.beta_multiplier == 0.95
