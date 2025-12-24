import pandas as pd

from pipeline.scenario_runner import run_scenarios
from pipeline.forecast_runner import run_forecast
from demo.refresh import _refresh_from_fixture


def main() -> int:
    _refresh_from_fixture("data/cache/sac_export.csv")
    run_forecast()
    result = run_scenarios()

    if int(result["scenario_count"]) < 3:
        print("Expected at least 3 scenarios.")
        return 1

    forecast = pd.read_csv("data/cache/forecast.csv")
    scenarios = pd.read_csv("data/cache/scenarios.csv")
    forecast_dates = list(forecast["date"])
    for name in scenarios["scenario"].unique():
        scenario_dates = list(scenarios[scenarios["scenario"] == name]["date"])
        if scenario_dates != forecast_dates:
            print("Scenario dates do not match forecast dates.")
            return 1

    print("SCENARIOS SMOKE OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
