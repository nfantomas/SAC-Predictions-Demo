from __future__ import annotations

from typing import Dict, Optional

import pandas as pd

from scenarios.schema import ScenarioParamsV3, migrate_params_v2_to_v3
from scenarios.v3 import DriverContext, apply_scenario_v3_simple
from model.cost_driver import calibrate_alpha_beta


def apply_scenario_v3(
    baseline_df: pd.DataFrame,
    params: ScenarioParamsV3,
    ctx_adapter: Optional[DriverContext],
    scenario_name: str,
) -> pd.DataFrame:
    if ctx_adapter is None:
        alpha, beta0 = calibrate_alpha_beta(float(baseline_df["yhat"].iloc[0]), 800, 0.2)
        ctx = DriverContext(alpha=alpha, beta0=beta0)
    else:
        ctx = ctx_adapter
    out = apply_scenario_v3_simple(baseline_df, params, ctx)
    out["scenario"] = scenario_name
    return out


def apply_presets_v3(
    baseline_df: pd.DataFrame,
    presets: Dict[str, ScenarioParamsV3],
) -> pd.DataFrame:
    frames = []
    for name, params in presets.items():
        frames.append(apply_scenario_v3(baseline_df, params, None, name))
    return pd.concat(frames, ignore_index=True)


def apply_migrated_v2(
    baseline_df: pd.DataFrame,
    params,
    scenario_name: str,
) -> pd.DataFrame:
    migrated = migrate_params_v2_to_v3(baseline_df, params)
    return apply_scenario_v3(baseline_df, migrated, None, scenario_name)
