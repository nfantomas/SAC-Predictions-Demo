import pandas as pd

from demo.refresh import _refresh_from_fixture
from pipeline.forecast_runner import run_forecast
from pipeline.scenario_runner import run_scenarios
from narrative.generator import generate_narrative, summarize_series
from scenarios.presets_v2 import PRESETS_V2


def main() -> int:
    _refresh_from_fixture("data/cache/sac_export.csv")
    run_forecast()
    run_scenarios()

    series = pd.read_csv("data/cache/sac_export.csv")
    stats = summarize_series(series)
    base_params = PRESETS_V2["base"]["params"]
    narrative = generate_narrative(
        stats,
        {
            "growth_delta_pp_per_year": base_params.growth_delta_pp_per_year,
            "shock_start_year": base_params.shock_start_year,
            "shock_pct": base_params.shock_pct,
            "shock_duration_months": base_params.shock_duration_months,
            "drift_pp_per_year": base_params.drift_pp_per_year,
        },
        "",
        use_llm=False,
    )
    required = {"mode", "title", "summary", "bullets", "assumptions"}
    if not required.issubset(narrative.keys()):
        print("Narrative output missing required fields.")
        return 1

    print("APP SMOKE OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
