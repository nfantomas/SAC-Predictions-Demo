from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

import numpy as np
import pandas as pd

from config import DEFAULT_ASSUMPTIONS
from scenarios.schema import ScenarioParamsV3
from scenarios.v3 import DriverContext, apply_scenario_v3_simple


@dataclass(frozen=True)
class SafetyBounds:
    max_multiplier: float = 3.0
    extreme_max_multiplier: float = 4.0
    max_monthly_jump_pct: float = 0.25  # 25% jump warning threshold


def _baseline_ctx() -> DriverContext:
    alpha = DEFAULT_ASSUMPTIONS.t0_cost * DEFAULT_ASSUMPTIONS.fixed_cost_share
    beta0 = (DEFAULT_ASSUMPTIONS.t0_cost * (1.0 - DEFAULT_ASSUMPTIONS.fixed_cost_share)) / DEFAULT_ASSUMPTIONS.t0_fte
    return DriverContext(alpha=alpha, beta0=beta0)


def validate_sanity_v3(params: ScenarioParamsV3, baseline: pd.DataFrame, bounds: SafetyBounds) -> Tuple[bool, List[str], List[str]]:
    """
    Lightweight safety check for presets/fixtures.
    Returns (ok, warnings, blocks).
    """
    warnings: List[str] = []
    blocks: List[str] = []

    if baseline.empty:
        return False, ["baseline_empty"], ["baseline_empty"]

    ctx = _baseline_ctx()
    baseline_min = float(baseline["yhat"].min())
    try:
        scenario = apply_scenario_v3_simple(baseline, params, context=ctx, horizon_months=len(baseline))
        start = float(scenario["yhat"].iloc[0])
        end = float(scenario["yhat"].iloc[-1])
        multiplier = 0.0 if start == 0 else end / start
    except Exception:
        multiplier = 1.0  # fallback estimate if simulation fails

    # Heuristic multiplier estimate to catch extremes even if simulation is flat
    est = 1.0 + (params.impact_magnitude or 0.0)
    if params.growth_delta_pp_per_year:
        est *= (1.0 + params.growth_delta_pp_per_year) ** (len(baseline) / 12.0)
    multiplier_est = max(multiplier, est)

    # If baseline itself is anomalously low vs alpha, treat as warning rather than block
    if baseline_min < ctx.alpha * 0.5 and multiplier_est > bounds.max_multiplier:
        warnings.append("Baseline contains an anomalous low point; multiplier check downgraded to warning.")
    else:
        if multiplier_est > bounds.extreme_max_multiplier:
            blocks.append(f"10y multiplier {multiplier_est:.2f}x exceeds extreme bound {bounds.extreme_max_multiplier}x.")
        elif multiplier_est > bounds.max_multiplier:
            warnings.append(f"10y multiplier {multiplier_est:.2f}x exceeds soft bound {bounds.max_multiplier}x.")

    # Monthly jump check (warning only)
    series = baseline["yhat"].astype(float).to_numpy()
    prev = series[:-1]
    curr = series[1:]
    jumps = np.abs(curr - prev) / np.maximum(prev, 1e-9)
    if np.any(jumps > bounds.max_monthly_jump_pct):
        warnings.append("Detected monthly jump exceeding threshold; review ramp/timing to smooth changes.")

    ok = len(blocks) == 0
    return ok, warnings, blocks
