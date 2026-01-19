from __future__ import annotations

from dataclasses import replace
from typing import Dict, List, Optional, Tuple

import pandas as pd

from scenarios.apply_scenario_v3 import apply_scenario_v3
from scenarios.schema import ScenarioParamsV3


class SuggestionValidationError(Exception):
    pass


_LEVEL_BOUNDS = (-0.5, 1.0)
_GROWTH_BOUNDS = (-0.5, 0.5)


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def validate_params_bounds(params: ScenarioParamsV3) -> Tuple[ScenarioParamsV3, List[str]]:
    warnings: List[str] = []
    impact_lower, impact_upper = (_LEVEL_BOUNDS if params.impact_mode == "level" else _GROWTH_BOUNDS)
    impact_magnitude = _clamp(params.impact_magnitude, impact_lower, impact_upper)
    if impact_magnitude != params.impact_magnitude:
        warnings.append("Clamped impact_magnitude to safety bounds.")

    growth_delta = _clamp(params.growth_delta_pp_per_year, -0.5, 0.5)
    if growth_delta != params.growth_delta_pp_per_year:
        warnings.append("Clamped growth_delta_pp_per_year to safety bounds.")

    drift = _clamp(params.drift_pp_per_year, -0.3, 0.3)
    if drift != params.drift_pp_per_year:
        warnings.append("Clamped drift_pp_per_year to safety bounds.")

    lag = _clamp(params.lag_months, 0, 60)
    onset = _clamp(params.onset_duration_months, 0, 24)

    event_duration = params.event_duration_months
    if event_duration is not None:
        event_duration = int(_clamp(event_duration, 0, 120))

    recovery_duration = params.recovery_duration_months
    if recovery_duration is not None:
        recovery_duration = int(_clamp(recovery_duration, 0, 60))

    updated = replace(
        params,
        impact_magnitude=impact_magnitude,
        growth_delta_pp_per_year=growth_delta,
        drift_pp_per_year=drift,
        lag_months=int(lag),
        onset_duration_months=int(onset),
        event_duration_months=event_duration,
        recovery_duration_months=recovery_duration,
    )
    return updated, warnings


def _simulate_multiplier(params: ScenarioParamsV3, months: int = 120) -> float:
    baseline_dates = pd.date_range("2026-01-01", periods=months, freq="MS")
    baseline = pd.DataFrame({"date": baseline_dates.date.astype(str), "yhat": [1.0] * months})
    scenario = apply_scenario_v3(baseline, params, "safety_check")
    first = scenario["yhat"].iloc[0]
    last = scenario["yhat"].iloc[-1]
    if first == 0:
        return 0.0
    return last / first


def _clamp_projection(params: ScenarioParamsV3, multiplier: float) -> Tuple[ScenarioParamsV3, str]:
    message = ""
    if multiplier > 3.0:
        factor = 3.0 / multiplier if multiplier != 0 else 0
        scaled_impact = params.impact_magnitude * factor
        scaled_growth = params.growth_delta_pp_per_year * factor
        scaled_drift = params.drift_pp_per_year * factor
        scaled_event_growth = (
            params.event_growth_delta_pp_per_year * factor if params.event_growth_delta_pp_per_year is not None else None
        )
        params = replace(
            params,
            impact_magnitude=scaled_impact,
            growth_delta_pp_per_year=scaled_growth,
            drift_pp_per_year=scaled_drift,
            event_growth_delta_pp_per_year=scaled_event_growth,
        )
        message = "Clamped scenario to keep 10y multiplier <= 3.0x."
    elif multiplier < 0.2:
        factor = multiplier / 0.2 if multiplier != 0 else 0
        scaled_impact = params.impact_magnitude * factor
        scaled_growth = params.growth_delta_pp_per_year * factor
        scaled_drift = params.drift_pp_per_year * factor
        scaled_event_growth = (
            params.event_growth_delta_pp_per_year * factor if params.event_growth_delta_pp_per_year is not None else None
        )
        params = replace(
            params,
            impact_magnitude=scaled_impact,
            growth_delta_pp_per_year=scaled_growth,
            drift_pp_per_year=scaled_drift,
            event_growth_delta_pp_per_year=scaled_event_growth,
        )
        message = "Clamped scenario to keep 10y multiplier >= 0.2x."
    return params, message


def validate_suggestion(params: Dict[str, object]) -> Tuple[ScenarioParamsV3, List[str]]:
    warnings: List[str] = []
    try:
        scenario_params = ScenarioParamsV3(**params)
    except Exception as exc:
        raise SuggestionValidationError(str(exc)) from exc

    scenario_params, bound_warnings = validate_params_bounds(scenario_params)
    warnings.extend(bound_warnings)

    multiplier = _simulate_multiplier(scenario_params)
    if multiplier > 3.0 or multiplier < 0.2:
        scenario_params, clamp_msg = _clamp_projection(scenario_params, multiplier)
        warnings.append(clamp_msg)
        multiplier = _simulate_multiplier(scenario_params)
        if multiplier > 3.0 or multiplier < 0.2:
            raise SuggestionValidationError(f"Projection multiplier {multiplier:.2f}x out of bounds after clamp.")

    return scenario_params, warnings
