from datetime import datetime, timezone

from scenarios.overlay_v2 import ScenarioParamsV2
from scenarios.validate import validate_params


def test_validate_params_clamps_and_warns():
    params = ScenarioParamsV2(
        growth_delta_pp_per_year=1.2,
        shock_start_year=datetime.now(timezone.utc).year - 1,
        shock_pct=-2.0,
        shock_duration_months=999,
        drift_pp_per_year=-2.0,
    )
    validated, warnings = validate_params(params, horizon_years=2)
    assert validated.growth_delta_pp_per_year == 0.5
    assert validated.shock_pct == -0.02
    assert validated.drift_pp_per_year == -0.5
    assert validated.shock_start_year is None
    assert validated.shock_duration_months == 24
    assert warnings
