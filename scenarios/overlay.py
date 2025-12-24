from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Optional

import pandas as pd


@dataclass(frozen=True)
class ScenarioParams:
    growth_delta_pp: float = 0.0
    shock_year: Optional[int] = None
    shock_pct: float = 0.0
    drift_pp_per_year: float = 0.0


def _apply_shock(value: float, year: int, shock_year: Optional[int], shock_pct: float) -> float:
    if shock_year and year >= shock_year:
        return value * (1.0 + shock_pct)
    return value


def apply_scenario(
    baseline_df: pd.DataFrame,
    params: ScenarioParams,
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

    first_value = _apply_shock(values[0], dates[0].year, params.shock_year, params.shock_pct)
    scenario_values = [max(0.0, first_value)]
    monthly_drift = params.drift_pp_per_year / 12.0

    for idx in range(1, len(values)):
        prev_base = values[idx - 1]
        curr_base = values[idx]
        base_growth = 0.0 if prev_base == 0 else (curr_base / prev_base) - 1.0
        drift = monthly_drift * idx
        adjusted_growth = base_growth + params.growth_delta_pp + drift
        next_value = scenario_values[-1] * (1.0 + adjusted_growth)
        next_value = _apply_shock(next_value, dates[idx].year, params.shock_year, params.shock_pct)
        scenario_values.append(max(0.0, next_value))

    scenario = pd.DataFrame(
        {
            "date": [d.isoformat() for d in dates],
            "scenario": scenario_name,
            "yhat": scenario_values,
        }
    )
    return scenario


def apply_presets(
    baseline_df: pd.DataFrame,
    presets: Dict[str, ScenarioParams],
) -> pd.DataFrame:
    frames = []
    for name in sorted(presets.keys()):
        frames.append(apply_scenario(baseline_df, presets[name], name))
    return pd.concat(frames, ignore_index=True)
