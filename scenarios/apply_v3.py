from __future__ import annotations

import pandas as pd

from model.cost_driver import calibrate_alpha_beta, cost_from_fte
from scenarios.schema import ScenarioParamsV3
from scenarios.v3 import apply_scenario_v3_simple, DriverContext


def apply_scenario_v3_hr(
    baseline_cost_df: pd.DataFrame,
    params: ScenarioParamsV3,
    alpha: float,
    beta: float,
    scenario_name: str,
) -> pd.DataFrame:
    ctx = DriverContext(alpha=alpha, beta0=beta)
    out = apply_scenario_v3_simple(baseline_cost_df, params, ctx)
    out["scenario"] = scenario_name
    return out
