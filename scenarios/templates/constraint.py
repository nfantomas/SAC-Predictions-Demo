from __future__ import annotations

from config import BASELINE_FTE_GROWTH_YOY
from scenarios.schema import ScenarioParamsV3


def build_cost_flat(lag_months: int, ramp_months: int) -> ScenarioParamsV3:
    return ScenarioParamsV3(
        driver="cost_target",
        lag_months=lag_months,
        onset_duration_months=ramp_months,
        cost_target_pct=0.0,
    )


def build_fte_flat(lag_months: int, ramp_months: int) -> ScenarioParamsV3:
    return ScenarioParamsV3(
        driver="fte",
        lag_months=lag_months,
        onset_duration_months=ramp_months,
        impact_mode="growth",
        growth_delta_pp_per_year=-BASELINE_FTE_GROWTH_YOY,
    )
