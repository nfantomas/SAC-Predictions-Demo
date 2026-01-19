from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

import pandas as pd

from scenarios.overlay_v2 import ScenarioParamsV2


Shape = Literal["step", "linear", "exp"]
ImpactMode = Literal["level", "growth"]
Driver = Literal["cost", "fte", "cost_target"]


@dataclass(frozen=True)
class ScenarioParamsV3:
    driver: Driver = "cost"
    lag_months: int = 0
    onset_duration_months: int = 0
    event_duration_months: Optional[int] = None
    recovery_duration_months: Optional[int] = None
    shape: Shape = "step"
    impact_mode: ImpactMode = "level"
    impact_magnitude: float = 0.0
    event_growth_delta_pp_per_year: Optional[float] = None
    event_growth_exp_multiplier: Optional[float] = None
    growth_delta_pp_per_year: float = 0.0
    drift_pp_per_year: float = 0.0
    post_event_growth_pp_per_year: Optional[float] = None
    fte_delta_abs: Optional[float] = None
    fte_delta_pct: Optional[float] = None
    beta_multiplier: Optional[float] = None
    inflation_by_segment: Optional[dict] = None
    segment_weights: Optional[dict] = None
    cost_target_pct: Optional[float] = None
    fte_cut_plan: Optional[dict] = None

    def __post_init__(self) -> None:
        errors = []
        if self.driver not in ("cost", "fte", "cost_target"):
            errors.append("driver must be one of: cost, fte, cost_target.")
        if not _is_int(self.lag_months):
            errors.append("lag_months must be a non-negative integer.")
        elif self.lag_months < 0:
            errors.append("lag_months must be >= 0.")

        if not _is_int(self.onset_duration_months):
            errors.append("onset_duration_months must be a non-negative integer.")
        elif self.onset_duration_months < 0:
            errors.append("onset_duration_months must be >= 0.")

        if self.event_duration_months is not None:
            if not _is_int(self.event_duration_months):
                errors.append("event_duration_months must be an integer when provided.")
            elif self.event_duration_months < 0:
                errors.append("event_duration_months must be >= 0 when provided.")

        if self.recovery_duration_months is not None:
            if not _is_int(self.recovery_duration_months):
                errors.append("recovery_duration_months must be an integer when provided.")
            elif self.recovery_duration_months < 0:
                errors.append("recovery_duration_months must be >= 0 when provided.")

        if self.shape not in ("step", "linear", "exp"):
            errors.append("shape must be one of: step, linear, exp.")

        if self.impact_mode not in ("level", "growth"):
            errors.append("impact_mode must be one of: level, growth.")

        if not isinstance(self.impact_magnitude, (int, float)):
            errors.append("impact_magnitude must be numeric.")

        if self.beta_multiplier is not None and self.beta_multiplier <= 0:
            errors.append("beta_multiplier must be positive when provided.")

        if self.cost_target_pct is not None and not isinstance(self.cost_target_pct, (int, float)):
            errors.append("cost_target_pct must be numeric when provided.")

        if self.fte_delta_abs is not None and not isinstance(self.fte_delta_abs, (int, float)):
            errors.append("fte_delta_abs must be numeric when provided.")

        if self.fte_delta_pct is not None and not isinstance(self.fte_delta_pct, (int, float)):
            errors.append("fte_delta_pct must be numeric when provided.")

        if errors:
            raise ValueError("; ".join(errors))


def migrate_params_v2_to_v3(
    baseline_df: pd.DataFrame,
    params: ScenarioParamsV2,
) -> ScenarioParamsV3:
    """
    Map V2 params (shock-based) to the V3 timeline model using baseline dates for anchoring.
    This preserves prior behavior for existing presets so downstream application can stay consistent.
    """
    if "date" not in baseline_df.columns:
        raise ValueError("baseline_df must include a date column for migration.")
    if baseline_df.empty:
        raise ValueError("baseline_df is empty; cannot anchor shock year.")

    baseline = baseline_df.copy()
    baseline["date"] = pd.to_datetime(baseline["date"], errors="raise")
    baseline = baseline.sort_values("date").reset_index(drop=True)

    shock_start_index: Optional[int] = None
    if params.shock_start_year:
        for idx, dt in enumerate(baseline["date"].dt.date.tolist()):
            if dt.year == params.shock_start_year:
                shock_start_index = idx
                break

    impact_magnitude = params.shock_pct if shock_start_index is not None else 0.0
    lag_months = shock_start_index or 0

    recovery_duration = None
    if params.shock_duration_months not in (None, 0):
        recovery_duration = 0

    return ScenarioParamsV3(
        lag_months=lag_months,
        onset_duration_months=0,
        event_duration_months=params.shock_duration_months,
        recovery_duration_months=recovery_duration,
        shape="step",
        impact_mode="level",
        impact_magnitude=impact_magnitude,
        event_growth_delta_pp_per_year=None,
        event_growth_exp_multiplier=None,
        growth_delta_pp_per_year=params.growth_delta_pp_per_year,
        drift_pp_per_year=params.drift_pp_per_year,
        post_event_growth_pp_per_year=None,
    )


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)
