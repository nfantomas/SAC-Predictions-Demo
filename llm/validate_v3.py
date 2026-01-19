from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from config import BASELINE_INFLATION_PPY, DEFAULT_ASSUMPTIONS
from llm.validate_suggestion import SuggestionValidationError
from scenarios.schema import ScenarioParamsV3
from scenarios.v3 import DriverContext, apply_scenario_v3_simple


@dataclass(frozen=True)
class ValidateContext:
    alpha: float = DEFAULT_ASSUMPTIONS.t0_cost * DEFAULT_ASSUMPTIONS.fixed_cost_share
    beta: float = (DEFAULT_ASSUMPTIONS.t0_cost * (1.0 - DEFAULT_ASSUMPTIONS.fixed_cost_share)) / DEFAULT_ASSUMPTIONS.t0_fte
    t0_cost: float = DEFAULT_ASSUMPTIONS.t0_cost
    inflation_ppy: float = BASELINE_INFLATION_PPY
    horizon_months: int = 120
    multiplier_max: float = 3.0
    multiplier_min: float = 0.2


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _scale_params(params: ScenarioParamsV3, factor: float) -> ScenarioParamsV3:
    return replace(
        params,
        impact_magnitude=params.impact_magnitude * factor,
        growth_delta_pp_per_year=params.growth_delta_pp_per_year * factor,
        drift_pp_per_year=params.drift_pp_per_year * factor,
        event_growth_delta_pp_per_year=(
            params.event_growth_delta_pp_per_year * factor if params.event_growth_delta_pp_per_year is not None else None
        ),
    )


def _bounded_params(params: ScenarioParamsV3) -> Tuple[ScenarioParamsV3, List[str]]:
    warnings: List[str] = []
    beta_multiplier = params.beta_multiplier
    if beta_multiplier is not None:
        clamped = _clamp(beta_multiplier, 0.7, 1.3)
        if clamped != beta_multiplier:
            warnings.append("Clamped beta_multiplier to [0.7, 1.3].")
            beta_multiplier = clamped

    impact_lower, impact_upper = (-0.5, 1.0) if params.impact_mode == "level" else (-0.5, 0.5)
    impact_magnitude = _clamp(params.impact_magnitude, impact_lower, impact_upper)
    if impact_magnitude != params.impact_magnitude:
        warnings.append("Clamped impact_magnitude to safety bounds.")

    growth_delta = _clamp(params.growth_delta_pp_per_year, -0.5, 0.5)
    if growth_delta != params.growth_delta_pp_per_year:
        warnings.append("Clamped growth_delta_pp_per_year to [-0.5, 0.5].")

    drift = _clamp(params.drift_pp_per_year, -0.3, 0.3)
    if drift != params.drift_pp_per_year:
        warnings.append("Clamped drift_pp_per_year to [-0.3, 0.3].")

    cost_target = params.cost_target_pct
    if cost_target is not None:
        clamped_ct = _clamp(cost_target, -0.5, 0.5)
        if clamped_ct != cost_target:
            warnings.append("Clamped cost_target_pct to [-0.5, 0.5].")
            cost_target = clamped_ct

    lag = int(_clamp(params.lag_months, 0, 60))
    onset = int(_clamp(params.onset_duration_months, 0, 24))

    updated = replace(
        params,
        beta_multiplier=beta_multiplier,
        impact_magnitude=impact_magnitude,
        growth_delta_pp_per_year=growth_delta,
        drift_pp_per_year=drift,
        cost_target_pct=cost_target,
        lag_months=lag,
        onset_duration_months=onset,
    )
    return updated, warnings


def _baseline_series(ctx: ValidateContext) -> pd.DataFrame:
    dates = pd.date_range("2028-01-01", periods=ctx.horizon_months, freq="MS")
    growth = (1.0 + ctx.inflation_ppy) ** (np.arange(ctx.horizon_months) / 12.0)
    yhat = ctx.t0_cost * growth
    return pd.DataFrame({"date": dates.date.astype(str), "yhat": yhat})


def validate_and_sanitize(params_raw: Dict[str, object], ctx: ValidateContext | None = None) -> Tuple[ScenarioParamsV3, List[str]]:
    ctx = ctx or ValidateContext()
    warnings: List[str] = []
    try:
        params = ScenarioParamsV3(**params_raw)
    except Exception as exc:
        raise SuggestionValidationError(str(exc)) from exc

    if params.lag_months < 0 or params.lag_months >= ctx.horizon_months:
        raise SuggestionValidationError("lag_months out of range for forecast horizon.")

    params, bound_warnings = _bounded_params(params)
    warnings.extend(bound_warnings)

    baseline = _baseline_series(ctx)
    driver_ctx = DriverContext(alpha=ctx.alpha, beta0=ctx.beta)

    scenario = apply_scenario_v3_simple(baseline, params, driver_ctx, horizon_months=ctx.horizon_months)
    start = float(scenario["yhat"].iloc[0])
    end = float(scenario["yhat"].iloc[-1])
    multiplier = 0.0 if start == 0 else end / start
    if multiplier > ctx.multiplier_max or multiplier < ctx.multiplier_min:
        factor = (ctx.multiplier_max / multiplier) if multiplier > ctx.multiplier_max and multiplier != 0 else (multiplier / ctx.multiplier_min if multiplier != 0 else 0)
        params = _scale_params(params, factor)
        warnings.append(f"Clamped to keep 10y multiplier within [{ctx.multiplier_min}x, {ctx.multiplier_max}x].")
        scenario = apply_scenario_v3_simple(baseline, params, driver_ctx, horizon_months=ctx.horizon_months)
        start = float(scenario["yhat"].iloc[0])
        end = float(scenario["yhat"].iloc[-1])
        multiplier = 0.0 if start == 0 else end / start
        if multiplier > ctx.multiplier_max or multiplier < ctx.multiplier_min:
            raise SuggestionValidationError(f"Projection multiplier {multiplier:.2f}x out of bounds after clamping.")

    min_cost = float(scenario["yhat"].min())
    if min_cost < ctx.alpha:
        factor = max(min_cost / ctx.alpha, 0.1)
        params = _scale_params(params, factor)
        warnings.append("Adjusted to enforce alpha cost floor.")
        scenario = apply_scenario_v3_simple(baseline, params, driver_ctx, horizon_months=ctx.horizon_months)
        if float(scenario["yhat"].min()) < ctx.alpha:
            raise SuggestionValidationError("Scenario violates alpha cost floor after clamping.")

    return params, warnings
