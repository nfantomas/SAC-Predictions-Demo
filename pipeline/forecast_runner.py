import json
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Dict

import pandas as pd

from forecast.baseline import BaselineConfig, run_baseline
from pipeline.cache import CacheError, load_cache


def run_forecast(
    cache_path: str = "data/cache/sac_export.csv",
    output_path: str = "data/cache/forecast.csv",
    meta_path: str = "data/cache/forecast_meta.json",
    horizon_months: int = 120,
) -> Dict[str, str]:
    try:
        rows, meta = load_cache(data_path=cache_path)
    except CacheError as exc:
        raise CacheError("Run `python -m demo.refresh --source sac` first.") from exc

    df = pd.DataFrame(rows)
    if df.empty:
        raise CacheError("Series cache is empty. Run demo.refresh again.")

    forecast_df = run_baseline(df, horizon_months=horizon_months, method="auto")
    forecast_df.to_csv(output_path, index=False)

    meta_out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "horizon_months": horizon_months,
        "method_used": forecast_df["method"].iloc[0] if not forecast_df.empty else "unknown",
        "input_min_date": meta.min_date,
        "input_max_date": meta.max_date,
        "output_min_date": forecast_df["date"].min(),
        "output_max_date": forecast_df["date"].max(),
    }
    with open(meta_path, "w", encoding="utf-8") as handle:
        json.dump(meta_out, handle, indent=2, sort_keys=True)

    return {
        "output_path": output_path,
        "meta_path": meta_path,
        "horizon_months": str(horizon_months),
    }
