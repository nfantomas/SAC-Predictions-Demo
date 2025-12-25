from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import pandas as pd


@dataclass(frozen=True)
class ScenarioParamsV2:
    growth_delta_pp_per_year: float = 0.0
    shock_start_year: Optional[int] = None
    shock_pct: float = 0.0
    shock_duration_months: Optional[int] = 12
    drift_pp_per_year: float = 0.0


def _apply_shock(value: float, index: int, shock_start_index: Optional[int], shock_duration: Optional[int], shock_pct: float) -> float:
    if shock_start_index is None:
        return value
    if index < shock_start_index:
        return value
    if shock_duration is None or shock_duration == 0:
        return value * (1.0 + shock_pct)
    if index < shock_start_index + shock_duration:
        return value * (1.0 + shock_pct)
    return value


def apply_scenario_v2(
    baseline_df: pd.DataFrame,
    params: ScenarioParamsV2,
    scenario_name: str,
) -> pd.DataFrame:
    if "date" not in baseline_df.columns or "yhat" not in baseline_df.columns:
        raise ValueError("baseline_df must include date and yhat columns.")
    if baseline_df.empty:
        raise ValueError("baseline_df is empty.")

    baseline = baseline_df.copy()
    baseline["date"] = pd.to_datetime(baseline["date"], errors="raise")
    baseline = baseline.sort_values("date").reset_index(drop=True)

    values = baseline["yhat"].astype(float).tolist()
    dates = baseline["date"].dt.date.tolist()

    monthly_growth_delta = params.growth_delta_pp_per_year / 12.0
    monthly_drift = params.drift_pp_per_year / 12.0

    shock_start_index = None
    if params.shock_start_year:
        for idx, dt in enumerate(dates):
            if dt.year == params.shock_start_year:
                shock_start_index = idx
                break

    scenario_values = [max(0.0, values[0])]
    for idx in range(1, len(values)):
        prev_base = values[idx - 1]
        curr_base = values[idx]
        base_growth = 0.0 if prev_base == 0 else (curr_base / prev_base) - 1.0
        adjusted_growth = base_growth + monthly_growth_delta + (monthly_drift * idx)
        adjusted_growth = max(-0.5, min(0.5, adjusted_growth))
        next_value = scenario_values[-1] * (1.0 + adjusted_growth)
        next_value = _apply_shock(
            next_value,
            idx,
            shock_start_index,
            params.shock_duration_months,
            params.shock_pct,
        )
        scenario_values.append(max(0.0, next_value))

    scenario = pd.DataFrame(
        {
            "date": [d.isoformat() for d in dates],
            "scenario": scenario_name,
            "yhat": scenario_values,
        }
    )
    return scenario


def apply_presets_v2(
    baseline_df: pd.DataFrame,
    presets: Dict[str, ScenarioParamsV2],
) -> pd.DataFrame:
    frames = []
    for name in sorted(presets.keys()):
        frames.append(apply_scenario_v2(baseline_df, presets[name], name))
    return pd.concat(frames, ignore_index=True)
