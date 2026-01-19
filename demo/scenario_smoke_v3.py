from __future__ import annotations

import sys

import pandas as pd

from config import Assumptions
from llm.validate_suggestion import validate_suggestion
from ui.assistant_v3_pipeline import apply_driver_scenario, build_driver_context


def _build_baseline():
    dates = pd.date_range("2026-01-01", periods=36, freq="MS")
    values = [10_000_000 * (1.01 ** i) for i in range(len(dates))]
    return pd.DataFrame({"date": dates.date.astype(str), "yhat": values})


def main() -> int:
    baseline = _build_baseline()
    params = {
        "lag_months": 1,
        "onset_duration_months": 3,
        "event_duration_months": 6,
        "recovery_duration_months": 6,
        "shape": "linear",
        "impact_mode": "level",
        "impact_magnitude": 0.05,
        "growth_delta_pp_per_year": 0.02,
        "drift_pp_per_year": 0.0,
    }
    validated, warnings = validate_suggestion(params)
    if warnings:
        print("Warnings:", " | ".join(warnings))

    ctx = build_driver_context(observed_t0_cost=10_000_000, assumptions=Assumptions(10_000_000, 0.2, 800, 0.2))
    scenario = apply_driver_scenario(baseline, validated, driver="cost", ctx=ctx, scenario_name="smoke")

    if scenario.empty or scenario["yhat"].isnull().any():
        print("SCENARIO V3 SMOKE FAILED: empty or null values")
        return 1

    print("SCENARIO V3 SMOKE OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
