import json
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Dict, Optional

import pandas as pd

from pipeline.cache import CacheError
from scenarios.overlay_v2 import apply_presets_v2
from scenarios.presets_v2 import PRESETS_V2
from scenarios.validate import validate_params


def _serialize_presets() -> Dict[str, Dict]:
    serialized = {}
    for name, preset in PRESETS_V2.items():
        serialized[name] = {
            "description": preset["description"],
            "story": preset["story"],
            "params": asdict(preset["params"]),
        }
    return serialized


def run_scenarios(
    forecast_path: str = "data/cache/forecast.csv",
    output_path: str = "data/cache/scenarios.csv",
    meta_path: str = "data/cache/scenarios_meta.json",
) -> Dict[str, str]:
    try:
        forecast_df = pd.read_csv(forecast_path)
    except FileNotFoundError as exc:
        raise CacheError("Run `python -m demo.forecast` first.") from exc

    if forecast_df.empty:
        raise CacheError("Forecast cache is empty. Run demo.forecast again.")

    horizon_years = len(pd.to_datetime(forecast_df["date"]).dt.year.unique())
    validated_presets = {}
    preset_warnings = {}
    for name, preset in PRESETS_V2.items():
        params, warnings = validate_params(preset["params"], horizon_years=horizon_years)
        validated_presets[name] = params
        if warnings:
            preset_warnings[name] = warnings

    scenarios_df = apply_presets_v2(
        forecast_df[["date", "yhat"]],
        validated_presets,
    )
    scenarios_df.to_csv(output_path, index=False)

    meta_out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "presets": _serialize_presets(),
        "preset_warnings": preset_warnings,
        "horizon_months": len(forecast_df),
        "output_min_date": scenarios_df["date"].min(),
        "output_max_date": scenarios_df["date"].max(),
    }
    with open(meta_path, "w", encoding="utf-8") as handle:
        json.dump(meta_out, handle, indent=2, sort_keys=True)

    return {
        "output_path": output_path,
        "meta_path": meta_path,
        "scenario_count": str(len(PRESETS_V2)),
    }
