from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from scenarios.overlay_v2 import ScenarioParamsV2


def validate_params(
    params: ScenarioParamsV2,
    horizon_years: Optional[int] = None,
) -> Tuple[ScenarioParamsV2, List[str]]:
    warnings: List[str] = []
    growth = params.growth_delta_pp_per_year
    shock_pct = params.shock_pct
    drift = params.drift_pp_per_year
    shock_year = params.shock_start_year
    duration = params.shock_duration_months

    if abs(shock_pct) > 1.5:
        shock_pct = shock_pct / 100.0
        warnings.append("Normalized shock_pct from percent to fraction.")

    if shock_pct < -0.9:
        shock_pct = -0.9
        warnings.append("Clamped shock_pct to -0.9.")
    if shock_pct > 1.0:
        shock_pct = 1.0
        warnings.append("Clamped shock_pct to 1.0.")

    if growth < -0.5:
        growth = -0.5
        warnings.append("Clamped growth_delta_pp_per_year to -0.5.")
    if growth > 0.5:
        growth = 0.5
        warnings.append("Clamped growth_delta_pp_per_year to 0.5.")

    if drift < -0.5:
        drift = -0.5
        warnings.append("Clamped drift_pp_per_year to -0.5.")
    if drift > 0.5:
        drift = 0.5
        warnings.append("Clamped drift_pp_per_year to 0.5.")

    if duration is not None and duration < 0:
        duration = 0
        warnings.append("Clamped shock_duration_months to 0.")

    if horizon_years:
        current_year = datetime.now(timezone.utc).year
        max_year = current_year + horizon_years
        if shock_year is not None and (shock_year < current_year or shock_year > max_year):
            shock_year = None
            warnings.append("Cleared shock_start_year outside forecast horizon.")
        max_duration = horizon_years * 12
        if duration is not None and duration > max_duration:
            duration = max_duration
            warnings.append("Clamped shock_duration_months to forecast horizon.")

    updated = replace(
        params,
        growth_delta_pp_per_year=growth,
        shock_pct=shock_pct,
        drift_pp_per_year=drift,
        shock_start_year=shock_year,
        shock_duration_months=duration,
    )
    return updated, warnings
