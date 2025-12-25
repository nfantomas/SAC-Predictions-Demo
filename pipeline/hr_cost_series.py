import os
from dataclasses import asdict, dataclass
from typing import Dict, Optional, Tuple

import pandas as pd

from config import load_config
from pipeline.cache import CacheError, build_meta, load_cache, save_cache
from pipeline.normalize_timeseries import NormalizeError, normalize_timeseries
from sac_connector.timeseries import DEFAULT_SLICE, fetch_timeseries


@dataclass(frozen=True)
class HrCostMeta:
    metric_name: str
    unit: str
    currency: str
    measure_used: str
    filters_used: Dict[str, str]
    aggregation: str
    provider_id: str
    namespace_id: str
    avg_cost_per_fte_monthly: float


DEFAULT_AVG_COST_PER_FTE = float(os.getenv("AVG_COST_PER_FTE_MONTHLY", "8000"))


def _build_hr_cost_meta(provider_id: str, namespace_id: str) -> HrCostMeta:
    return HrCostMeta(
        metric_name="hr_cost",
        unit="monthly_cost",
        currency="EUR",
        measure_used="SignedData",
        filters_used=DEFAULT_SLICE.filters,
        aggregation="sum_by_month",
        provider_id=provider_id,
        namespace_id=namespace_id,
        avg_cost_per_fte_monthly=DEFAULT_AVG_COST_PER_FTE,
    )


def get_hr_cost_series(
    source: str = "sac",
    refresh: bool = False,
    cache_path: str = "data/cache/sac_export.csv",
) -> Tuple[pd.DataFrame, Dict[str, object]]:
    if source == "cache":
        rows, meta = load_cache(data_path=cache_path)
        df = pd.DataFrame(rows)
        df["value"] = df["value"].astype(float)
        return df, {**asdict(_build_hr_cost_meta("unknown", "unknown")), **asdict(meta)}

    if source == "fixture":
        fixture_path = "tests/fixtures/sample_series.csv"
        if not os.path.exists(fixture_path):
            raise CacheError("Fixture missing: tests/fixtures/sample_series.csv")
        df = pd.read_csv(fixture_path)
        if df.empty:
            raise CacheError("Fixture is empty.")
        df["value"] = df["value"].astype(float) * DEFAULT_AVG_COST_PER_FTE
        rows = df.to_dict(orient="records")
        meta = build_meta(rows, source="fixture")
        extra = asdict(_build_hr_cost_meta("fixture", "fixture"))
        save_cache(rows, meta, data_path=cache_path, extra_meta=extra)
        return df, {**extra, **asdict(meta)}

    cfg = load_config()
    provider_id = cfg.provider_id
    namespace_id = cfg.namespace_id or "sac"
    if not provider_id:
        raise CacheError("Missing SAC_PROVIDER_ID for HR cost series.")

    raw_df = fetch_timeseries(
        provider_id=provider_id,
        namespace_id=namespace_id,
        config=cfg,
        slice_spec=DEFAULT_SLICE,
    )
    try:
        normalized = normalize_timeseries(raw_df)
    except NormalizeError as exc:
        raise CacheError(str(exc)) from exc

    normalized["value"] = normalized["value"].astype(float) * DEFAULT_AVG_COST_PER_FTE
    rows = normalized.to_dict(orient="records")
    meta = build_meta(rows, source="sac")
    extra = asdict(_build_hr_cost_meta(provider_id, namespace_id))
    save_cache(rows, meta, data_path=cache_path, extra_meta=extra)
    return normalized, {**extra, **asdict(meta)}
