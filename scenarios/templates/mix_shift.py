from __future__ import annotations

from scenarios.schema import ScenarioParamsV3


def build_params(lag_months: int, ramp_months: int, magnitude_pct: float) -> ScenarioParamsV3:
    return ScenarioParamsV3(
        driver="cost",
        lag_months=lag_months,
        onset_duration_months=ramp_months,
        beta_multiplier=1.0 + magnitude_pct,
        impact_mode="level",
        impact_magnitude=0.0,
    )
