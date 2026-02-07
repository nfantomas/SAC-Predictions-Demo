from scenarios.normalize_params import normalize_params
from scenarios.schema import ScenarioParamsV3


def test_normalizes_whole_number_percent():
    params = ScenarioParamsV3(
        impact_magnitude=5.0,
        growth_delta_pp_per_year=-10.0,
        drift_pp_per_year=0.08,
        fte_delta_pct=2.0,
        cost_target_pct=-15.0,
    )
    normalized, warnings = normalize_params(params)
    assert normalized.impact_magnitude == 0.05
    assert normalized.growth_delta_pp_per_year == -0.1
    assert normalized.drift_pp_per_year == 0.08
    assert normalized.fte_delta_pct == 0.02
    assert normalized.cost_target_pct == -0.15
    assert len(warnings) == 4


def test_no_change_for_decimals():
    params = ScenarioParamsV3(
        impact_magnitude=0.05,
        growth_delta_pp_per_year=-0.1,
        fte_delta_pct=-0.08,
        cost_target_pct=-0.1,
    )
    normalized, warnings = normalize_params(params)
    assert normalized == params
    assert warnings == []
