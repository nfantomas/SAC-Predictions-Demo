from __future__ import annotations

from scenarios.schema import ScenarioParamsV3


def build_params(lag_months: int, ramp_months: int, magnitude_pct: float) -> ScenarioParamsV3:
    return ScenarioParamsV3(
        driver="fte",
        lag_months=lag_months,
        onset_duration_months=ramp_months,
        fte_delta_pct=magnitude_pct,
    )
