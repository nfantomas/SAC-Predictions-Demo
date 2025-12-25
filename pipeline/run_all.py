from typing import Dict

from pipeline.cache import CacheError, load_cache
from demo.refresh import refresh_from_sac
from pipeline.forecast_runner import run_forecast
from pipeline.scenario_runner import run_scenarios


def run_all(cache_path: str = "data/cache/sac_export.csv") -> Dict[str, object]:
    refresh_used_cache = False
    try:
        refresh_from_sac(cache_path)
    except Exception as exc:
        try:
            load_cache(data_path=cache_path)
        except CacheError:
            return {"ok": False, "error": str(exc), "refresh_used_cache": False}
        refresh_used_cache = True

    forecast_result = run_forecast()
    scenario_result = run_scenarios()
    return {
        "ok": True,
        "refresh_used_cache": refresh_used_cache,
        "forecast": forecast_result,
        "scenarios": scenario_result,
    }
