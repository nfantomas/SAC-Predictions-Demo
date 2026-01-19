from __future__ import annotations

from dataclasses import replace
from typing import Dict, List, Tuple

import pandas as pd

from scenarios.apply_v3 import apply_scenario_v3_hr
from scenarios.schema import ScenarioParamsV3


class ScenarioValidationError(Exception):
    pass


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def validate_params_v3(params: ScenarioParamsV3) -> Tuple[ScenarioParamsV3, List[str]]:
    warnings: List[str] = []
    beta_multiplier = params.beta_multiplier
    if beta_multiplier is not None:
        clamped = _clamp(beta_multiplier, 0.7, 1.2)
        if clamped != beta_multiplier:
            warnings.append("Clamped beta_multiplier to [0.7, 1.2].")
            beta_multiplier = clamped

    impact_magnitude = params.impact_magnitude
    if params.impact_mode == "level":
        impact_magnitude = _clamp(impact_magnitude, -0.5, 1.0)
    else:
        impact_magnitude = _clamp(impact_magnitude, -0.5, 0.5)
    if impact_magnitude != params.impact_magnitude:
        warnings.append("Clamped impact_magnitude to safety bounds.")

    growth_delta = _clamp(params.growth_delta_pp_per_year, -0.5, 0.5)
    if growth_delta != params.growth_delta_pp_per_year:
        warnings.append("Clamped growth_delta_pp_per_year to [-0.5, 0.5].")

    drift = _clamp(params.drift_pp_per_year, -0.3, 0.3)
    if drift != params.drift_pp_per_year:
        warnings.append("Clamped drift_pp_per_year to [-0.3, 0.3].")

    inflation_by_segment = params.inflation_by_segment
    if inflation_by_segment:
        bounded = {}
        for k, v in inflation_by_segment.items():
            bounded[k] = _clamp(float(v), -0.1, 0.2)
        if bounded != inflation_by_segment:
            warnings.append("Clamped inflation_by_segment to [-0.1, 0.2].")
            inflation_by_segment = bounded

    updated = replace(
        params,
        beta_multiplier=beta_multiplier,
        impact_magnitude=impact_magnitude,
        growth_delta_pp_per_year=growth_delta,
        drift_pp_per_year=drift,
        inflation_by_segment=inflation_by_segment,
    )
    return updated, warnings


def validate_projection(
    baseline_cost_df: pd.DataFrame,
    params: ScenarioParamsV3,
    alpha: float,
    beta: float,
    multiplier_max: float = 3.0,
    multiplier_min: float = 0.2,
) -> Tuple[ScenarioParamsV3, List[str]]:
    params, warnings = validate_params_v3(params)
    scenario = apply_scenario_v3_hr(baseline_cost_df, params, alpha=alpha, beta=beta, scenario_name="safety_check")
    start = float(scenario["yhat"].iloc[0])
    end = float(scenario["yhat"].iloc[-1])
    multiplier = 0.0 if start == 0 else end / start
    if multiplier > multiplier_max or multiplier < multiplier_min:
        if multiplier > multiplier_max:
            factor = multiplier_max / multiplier if multiplier != 0 else 0
            warnings.append(f"Clamped projection multiplier to <= {multiplier_max}x.")
        else:
            factor = multiplier / multiplier_min if multiplier != 0 else 0
            warnings.append(f"Clamped projection multiplier to >= {multiplier_min}x.")
        scaled = replace(
            params,
            impact_magnitude=params.impact_magnitude * factor,
            growth_delta_pp_per_year=params.growth_delta_pp_per_year * factor,
        )
        scenario = apply_scenario_v3_hr(baseline_cost_df, scaled, alpha=alpha, beta=beta, scenario_name="safety_check")
        start = float(scenario["yhat"].iloc[0])
        end = float(scenario["yhat"].iloc[-1])
        multiplier = 0.0 if start == 0 else end / start
        if multiplier > multiplier_max or multiplier < multiplier_min:
            second_factor = (multiplier_max / multiplier) if multiplier > multiplier_max and multiplier != 0 else (multiplier / multiplier_min if multiplier != 0 else 0)
            scaled = replace(
                scaled,
                impact_magnitude=scaled.impact_magnitude * second_factor,
                growth_delta_pp_per_year=scaled.growth_delta_pp_per_year * second_factor,
            )
            warnings.append("Applied additional clamp to keep projection within bounds.")
        return scaled, warnings
    return params, warnings
