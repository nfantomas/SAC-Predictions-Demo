from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional

import pandas as pd

from model.cost_driver import calibrate_alpha_beta, cost_from_fte, project_beta
from scenarios.profile import profile_factor
from scenarios.schema import ScenarioParamsV3, migrate_params_v2_to_v3


@dataclass(frozen=True)
class DriverContext:
    alpha: float
    beta0: float


def apply_fte_step_or_ramp(fte_series: pd.Series, delta: float, start_idx: int, ramp_months: int) -> pd.Series:
    adjusted = fte_series.copy()
    if ramp_months <= 0:
        adjusted[start_idx:] = (fte_series[start_idx:] * (1.0 + delta)).clip(lower=0.0)
        return adjusted
    for offset in range(len(fte_series) - start_idx):
        idx = start_idx + offset
        factor = profile_factor("linear", offset, ramp_months)
        adjusted[idx] = fte_series[idx] * (1.0 + delta * factor)
    return adjusted.clip(lower=0.0)


def apply_beta_level_reset(beta_series: pd.Series, pct: float, start_idx: int) -> pd.Series:
    adjusted = beta_series.copy()
    adjusted[start_idx:] = beta_series[start_idx:] * (1.0 + pct)
    return adjusted


def apply_beta_temporary_delta(beta_series: pd.Series, pct: float, start_idx: int, duration_months: int, ramp_months: int) -> pd.Series:
    adjusted = beta_series.copy()
    end_idx = min(len(beta_series), start_idx + duration_months) if duration_months else len(beta_series)
    for offset in range(start_idx, end_idx):
        ramp_offset = offset - start_idx
        factor = profile_factor("linear", ramp_offset, ramp_months) if ramp_months else 1.0
        adjusted[offset] = beta_series[offset] * (1.0 + pct * factor)
    return adjusted


def apply_scenario_v3_simple(
    baseline_cost_df: pd.DataFrame,
    params: ScenarioParamsV3,
    context: Optional[DriverContext] = None,
    horizon_months: Optional[int] = None,
) -> pd.DataFrame:
    if baseline_cost_df.empty:
        raise ValueError("baseline_cost_df is empty.")

    baseline_cost = baseline_cost_df.copy()
    baseline_cost["date"] = pd.to_datetime(baseline_cost["date"])
    baseline_cost = baseline_cost.sort_values("date").reset_index(drop=True)
    horizon = horizon_months or len(baseline_cost)

    if context is None:
        first_cost = float(baseline_cost["yhat"].iloc[0])
        alpha, beta0 = calibrate_alpha_beta(first_cost, max(first_cost / 12_500.0, 1.0), 0.2)
    else:
        alpha, beta0 = context.alpha, context.beta0

    beta_series = project_beta(beta0, months=horizon)
    # Infer FTE from baseline path using the projected beta trajectory so we do not double-count inflation.
    variable_cost = (baseline_cost["yhat"].iloc[:horizon] - alpha).clip(lower=0.0)
    fte_series = variable_cost / beta_series.iloc[:horizon]

    # Apply FTE changes
    if params.fte_delta_pct:
        fte_series = apply_fte_step_or_ramp(
            fte_series.copy(), delta=params.fte_delta_pct, start_idx=params.lag_months, ramp_months=params.onset_duration_months
        )
    if params.fte_delta_abs:
        fte0 = fte_series.iloc[0]
        delta_pct = params.fte_delta_abs / fte0 if fte0 else 0.0
        fte_series = apply_fte_step_or_ramp(
            fte_series.copy(), delta=delta_pct, start_idx=params.lag_months, ramp_months=params.onset_duration_months
        )

    # Apply growth delta (pp/year) to FTE path to approximate slower/faster business growth.
    if params.growth_delta_pp_per_year:
        monthly_delta = (1.0 + params.growth_delta_pp_per_year) ** (1 / 12.0) - 1.0
        adjusted = fte_series.copy()
        for offset in range(len(fte_series) - params.lag_months):
            idx = params.lag_months + offset
            ramp_factor = profile_factor("linear", offset, params.onset_duration_months)
            rate = monthly_delta * ramp_factor
            if rate:
                adjusted[idx:] = adjusted[idx:] * (1.0 + rate)
        fte_series = adjusted

    # Apply beta changes
    beta_eff = beta_series
    if params.beta_multiplier:
        beta_eff = apply_beta_level_reset(beta_eff, pct=params.beta_multiplier - 1.0, start_idx=params.lag_months)
    if params.cost_target_pct:
        # Convert cost target into an effective FTE delta on variable portion
        target_cost = baseline_cost["yhat"].iloc[0] * (1.0 + params.cost_target_pct)
        fte0 = fte_series.iloc[0]
        variable_target = max(0.0, target_cost - alpha)
        delta_pct = (variable_target / beta_series.iloc[0] / fte0) - 1.0 if fte0 else 0.0
        fte_series = apply_fte_step_or_ramp(
            fte_series, delta=delta_pct, start_idx=params.lag_months, ramp_months=params.onset_duration_months
        )

    costs = cost_from_fte(alpha, beta_eff.iloc[:horizon], fte_series.iloc[:horizon])
    out = pd.DataFrame({"date": baseline_cost["date"].iloc[:horizon].dt.date.astype(str), "yhat": costs.values})
    out["scenario"] = params.driver or "scenario"
    return out


def apply_migrated_v2(baseline_df: pd.DataFrame, params, scenario_name: str) -> pd.DataFrame:
    migrated = migrate_params_v2_to_v3(baseline_df, params)
    alpha, beta0 = calibrate_alpha_beta(float(baseline_df["yhat"].iloc[0]), 800, 0.2)
    ctx = DriverContext(alpha=alpha, beta0=beta0)
    out = apply_scenario_v3_simple(baseline_df, migrated, ctx)
    out["scenario"] = scenario_name
    return out
