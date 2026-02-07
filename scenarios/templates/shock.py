from __future__ import annotations

from scenarios.schema import ScenarioParamsV3


def build_params(
    lag_months: int,
    ramp_months: int,
    duration_months: int | None,
    magnitude_pct: float,
) -> ScenarioParamsV3:
    return ScenarioParamsV3(
        driver="cost",
        lag_months=lag_months,
        onset_duration_months=ramp_months,
        event_duration_months=duration_months,
        impact_mode="level",
        impact_magnitude=magnitude_pct,
    )
