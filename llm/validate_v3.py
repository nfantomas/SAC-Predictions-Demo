from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from config import BASELINE_INFLATION_PPY, DEFAULT_ASSUMPTIONS
from config.core import VALIDATION_CAPS
from config.validation_caps import caps_for_severity
from llm.validate_suggestion import SuggestionValidationError
from llm.validation_result import ValidationIssue, ValidationResult, summarize_warnings
from scenarios.schema import ScenarioParamsV3
from scenarios.v3 import DriverContext, apply_scenario_v3_simple
from scenarios.normalize_params import normalize_params


@dataclass(frozen=True)
class ValidateContext:
    alpha: float = DEFAULT_ASSUMPTIONS.t0_cost * DEFAULT_ASSUMPTIONS.fixed_cost_share
    beta: float = (DEFAULT_ASSUMPTIONS.t0_cost * (1.0 - DEFAULT_ASSUMPTIONS.fixed_cost_share)) / DEFAULT_ASSUMPTIONS.t0_fte
    t0_cost: float = DEFAULT_ASSUMPTIONS.t0_cost
    inflation_ppy: float = BASELINE_INFLATION_PPY
    horizon_months: int = 120
    multiplier_max: float = 3.0
    multiplier_min: float = 0.2
    severity: str = "operational"


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _scale_params(params: ScenarioParamsV3, factor: float) -> ScenarioParamsV3:
    return replace(
        params,
        impact_magnitude=params.impact_magnitude * factor,
        growth_delta_pp_per_year=params.growth_delta_pp_per_year * factor,
        drift_pp_per_year=params.drift_pp_per_year * factor,
        fte_delta_pct=(params.fte_delta_pct * factor if params.fte_delta_pct is not None else None),
        fte_delta_abs=(params.fte_delta_abs * factor if params.fte_delta_abs is not None else None),
        cost_target_pct=(params.cost_target_pct * factor if params.cost_target_pct is not None else None),
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
    """
    Legacy signature: raises on hard failures, returns (params, warnings) otherwise.
    """
    params, warnings, result = validate_and_sanitize_result(params_raw, ctx=ctx)
    if result.errors:
        raise SuggestionValidationError("; ".join([iss.message for iss in result.errors]))
    return params, warnings


def validate_and_sanitize_result(params_raw: Dict[str, object], ctx: ValidateContext | None = None) -> Tuple[ScenarioParamsV3, List[str], ValidationResult]:
    ctx = ctx or ValidateContext()
    caps = caps_for_severity(ctx.severity)
    warnings: List[str] = []
    errors: List[ValidationIssue] = []
    clamps: List[ValidationIssue] = []
    try:
        params = ScenarioParamsV3(**params_raw)
    except Exception as exc:
        errors.append(ValidationIssue(str(exc)))
        return ScenarioParamsV3(), warnings, ValidationResult(errors=errors, warnings=[], clamps=clamps)  # type: ignore[arg-type]

    params, normalization_warnings = normalize_params(params)
    warnings.extend(normalization_warnings)

    if params.lag_months < 0 or params.lag_months >= ctx.horizon_months:
        errors.append(ValidationIssue("lag_months out of range for forecast horizon."))
        return params, warnings, ValidationResult(errors=errors, warnings=[], clamps=clamps)

    # Hard invariant: fixed component cannot exceed configured t0 total cost.
    if ctx.alpha > ctx.t0_cost:
        errors.append(ValidationIssue("alpha > cost_at_t0 is invalid (negative variable cost)."))
        return params, warnings, ValidationResult(errors=errors, warnings=[], clamps=clamps)

    params, bound_warnings = _bounded_params(params)
    warnings.extend(bound_warnings)

    baseline = _baseline_series(ctx)
    driver_ctx = DriverContext(alpha=ctx.alpha, beta0=ctx.beta)

    scenario = apply_scenario_v3_simple(baseline, params, driver_ctx, horizon_months=ctx.horizon_months)
    if scenario["yhat"].isnull().any() or not np.isfinite(scenario["yhat"]).all():
        errors.append(ValidationIssue("Scenario contains NaN/inf values."))
        return params, warnings, ValidationResult(errors=errors, warnings=[], clamps=clamps)

    # Soft-clamp loop for projection/momentum instead of blocking.
    for _ in range(6):
        start_val = float(scenario["yhat"].iloc[0])
        end_val = float(scenario["yhat"].iloc[-1])
        multiplier_raw = (end_val / start_val) if start_val else 1.0
        pct_changes = scenario["yhat"].astype(float).pct_change().fillna(0.0).abs()
        shock_like = (params.impact_mode == "level" and abs(params.impact_magnitude) >= 0.1) or (
            params.beta_multiplier and abs(params.beta_multiplier - 1.0) >= 0.1
        )
        cap = caps["mom_cap_shock"] if shock_like else caps["mom_cap_default"]
        max_jump = float(pct_changes.max()) if len(pct_changes) else 0.0

        need_multiplier_clamp = multiplier_raw > ctx.multiplier_max or multiplier_raw < ctx.multiplier_min
        need_mom_clamp = max_jump > cap
        if not need_multiplier_clamp and not need_mom_clamp:
            break

        factor = 1.0
        if multiplier_raw > ctx.multiplier_max:
            factor = min(factor, ctx.multiplier_max / multiplier_raw)
        elif multiplier_raw < ctx.multiplier_min and multiplier_raw > 0:
            factor = min(factor, multiplier_raw / ctx.multiplier_min)
        if need_mom_clamp and max_jump > 0:
            factor = min(factor, cap / max_jump)

        # Do not spin forever; if we cannot improve by scaling, keep fail-open with warnings.
        if factor >= 0.999:
            if need_multiplier_clamp:
                warnings.append(
                    f"Projection multiplier {multiplier_raw:.2f}x outside [{ctx.multiplier_min}x, {ctx.multiplier_max}x]."
                )
            if need_mom_clamp:
                clamps.append(ValidationIssue(f"Monthly change exceeded {cap:.0%}; review ramp/timing."))
            break

        params = _scale_params(params, factor)
        clamps.append(ValidationIssue(f"Applied safety scaling factor {factor:.3f} to keep scenario within guardrails."))
        scenario = apply_scenario_v3_simple(baseline, params, driver_ctx, horizon_months=ctx.horizon_months)
        if scenario["yhat"].isnull().any() or not np.isfinite(scenario["yhat"]).all():
            errors.append(ValidationIssue("Scenario contains NaN/inf values after safety scaling."))
            return params, warnings, ValidationResult(errors=errors, warnings=[], clamps=clamps)

    # Alpha floor / non-negativity
    if (scenario["yhat"] < 0).any():
        errors.append(ValidationIssue("Scenario produces negative costs."))
    # Implied FTE path
    fte_series = (scenario["yhat"] - ctx.alpha) / ctx.beta
    if fte_series.isnull().any() or not np.isfinite(fte_series).all():
        warnings.append("Implied FTE contains NaN/inf values; check parameter coherence.")
    if (fte_series < 0).any():
        warnings.append("Implied FTE drops below zero in this path; consider softer ramp/impact.")

    # CAGR caps (hard)
    years = ctx.horizon_months / 12.0
    start_cost = float(scenario["yhat"].iloc[0])
    end_cost = float(scenario["yhat"].iloc[-1])
    cost_cagr = ((end_cost / start_cost) ** (1 / years) - 1) if start_cost > 0 else 0.0
    start_fte = float(fte_series.iloc[0])
    end_fte = float(fte_series.iloc[-1])
    fte_cagr = ((end_fte / start_fte) ** (1 / years) - 1) if start_fte > 0 else 0.0
    cost_cagr_min = caps["cost_cagr_min"]
    cost_cagr_max = caps["cost_cagr_max"]
    fte_cagr_min = caps["fte_cagr_min"]
    fte_cagr_max = caps["fte_cagr_max"]
    if cost_cagr < cost_cagr_min or cost_cagr > cost_cagr_max:
        warnings.append(f"Cost CAGR {cost_cagr:.2%} outside [{cost_cagr_min:.0%}, {cost_cagr_max:.0%}].")
    if fte_cagr < fte_cagr_min or fte_cagr > fte_cagr_max:
        warnings.append(f"FTE CAGR {fte_cagr:.2%} outside [{fte_cagr_min:.0%}, {fte_cagr_max:.0%}].")

    # MoM stability warning if still high after scaling attempts.
    pct_changes = scenario["yhat"].astype(float).pct_change().fillna(0.0).abs()
    shock_like = (params.impact_mode == "level" and abs(params.impact_magnitude) >= 0.1) or (
        params.beta_multiplier and abs(params.beta_multiplier - 1.0) >= 0.1
    )
    cap = caps["mom_cap_shock"] if shock_like else caps["mom_cap_default"]
    if (pct_changes > cap).any():
        clamps.append(ValidationIssue(f"Monthly change exceeded {cap:.0%}; review ramp/timing."))

    # Baseline deviation warnings at Year-10
    base_cost_y10 = float(baseline["yhat"].iloc[-1])
    scen_cost_y10 = end_cost
    if base_cost_y10 > 0:
        ratio = scen_cost_y10 / base_cost_y10
        if ratio < caps["baseline_dev_warn_low"] or ratio > caps["baseline_dev_warn_high"]:
            warnings.append(f"Scenario cost deviates from baseline by {ratio:.2f}× at Year-10.")
    base_fte_y10 = float(((baseline["yhat"] - ctx.alpha) / ctx.beta).iloc[-1])
    if base_fte_y10 > 0 and end_fte is not None:
        ratio_fte = end_fte / base_fte_y10
        if ratio_fte < caps["baseline_dev_warn_low"] or ratio_fte > caps["baseline_dev_warn_high"]:
            warnings.append(f"Scenario FTE deviates from baseline by {ratio_fte:.2f}× at Year-10.")

    summary, details = summarize_warnings(
        warnings=warnings,
        clamps=[c.message for c in clamps],
        normalizations=normalization_warnings,
        max_items=5,
    )

    result = ValidationResult(
        errors=errors,
        warnings=[ValidationIssue(m) for m in details],
        clamps=[ValidationIssue(m) for m in summary],
    )
    if errors:
        return params, warnings, result
    return params, summary, result
