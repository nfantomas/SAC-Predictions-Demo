from __future__ import annotations

from config import BASELINE_FTE_GROWTH_YOY
from scenarios.schema import ScenarioParamsV3


def build_params(lag_months: int, ramp_months: int, duration_months: int | None, magnitude_pct: float) -> ScenarioParamsV3:
    growth_delta = -BASELINE_FTE_GROWTH_YOY
    fte_delta_pct = None
    if magnitude_pct:
        fte_delta_pct = magnitude_pct
        growth_delta = 0.0
    return ScenarioParamsV3(
        driver="fte",
        lag_months=lag_months,
        onset_duration_months=ramp_months,
        event_duration_months=duration_months,
        impact_mode="growth",
        impact_magnitude=0.0,
        growth_delta_pp_per_year=growth_delta,
        fte_delta_pct=fte_delta_pct,
    )
