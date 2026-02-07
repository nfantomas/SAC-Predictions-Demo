from __future__ import annotations

from scenarios.schema import ScenarioParamsV3


def build_params(lag_months: int, ramp_months: int, magnitude_pct: float) -> ScenarioParamsV3:
    return ScenarioParamsV3(
        driver="cost_target",
        lag_months=lag_months,
        onset_duration_months=ramp_months,
        cost_target_pct=magnitude_pct,
    )
