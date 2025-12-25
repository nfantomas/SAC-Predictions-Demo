import os
from dataclasses import asdict, dataclass
from typing import Dict, Optional, Tuple

import pandas as pd

from config import load_config
from pipeline.cache import CacheError, build_meta, load_cache, save_cache
from pipeline.metric_mapping import MetricMappingError, get_metric_mapping
from pipeline.normalize_timeseries import NormalizeError, NormalizeSpec, normalize_timeseries
from sac_connector.timeseries import SliceSpec, fetch_timeseries


@dataclass(frozen=True)
class HrCostMeta:
    metric_name: str
    unit: str
    currency: str
    measure_used: str
    filters_used: Dict[str, str]
    grain: str
    aggregation: str
    provider_id: str
    namespace_id: str
    provider_name: str
    avg_cost_per_fte_monthly: float
    calculation: str


DEFAULT_AVG_COST_PER_FTE = float(os.getenv("AVG_COST_PER_FTE_MONTHLY", "8000"))


def _build_hr_cost_meta(provider_id: str, namespace_id: str, provider_name: str) -> HrCostMeta:
    mapping = get_metric_mapping()
    return HrCostMeta(
        metric_name=mapping.metric_name,
        unit=mapping.unit,
        currency=mapping.currency,
        measure_used=mapping.measure,
        filters_used=mapping.filters,
        grain=mapping.grain,
        aggregation="sum_by_month",
        provider_id=provider_id,
        namespace_id=namespace_id,
        provider_name=provider_name,
        avg_cost_per_fte_monthly=DEFAULT_AVG_COST_PER_FTE,
        calculation=mapping.calculation,
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
        return df, {**asdict(_build_hr_cost_meta("unknown", "unknown", "unknown")), **asdict(meta)}

    if source == "fixture":
        fixture_path = "tests/fixtures/sample_series.csv"
        if not os.path.exists(fixture_path):
            raise CacheError("Fixture missing: tests/fixtures/sample_series.csv")
        df = pd.read_csv(fixture_path)
        if df.empty:
            raise CacheError("Fixture is empty.")
        mapping = get_metric_mapping()
        if mapping.measure != "Cost":
            df["value"] = df["value"].astype(float) * DEFAULT_AVG_COST_PER_FTE
        else:
            df["value"] = df["value"].astype(float)
        rows = df.to_dict(orient="records")
        meta = build_meta(rows, source="fixture")
        extra = asdict(_build_hr_cost_meta("fixture", "fixture", "fixture"))
        save_cache(rows, meta, data_path=cache_path, extra_meta=extra)
        return df, {**extra, **asdict(meta)}

    cfg = load_config()
    provider_id = cfg.provider_id
    namespace_id = cfg.namespace_id or "sac"
    provider_name = cfg.provider_name or "SAC model"
    if not provider_id:
        raise CacheError("Missing SAC_PROVIDER_ID for HR cost series.")
    try:
        mapping = get_metric_mapping()
    except MetricMappingError as exc:
        raise CacheError(str(exc)) from exc

    raw_df = fetch_timeseries(
        provider_id=provider_id,
        namespace_id=namespace_id,
        config=cfg,
        slice_spec=SliceSpec(measure=mapping.measure, filters=mapping.filters),
    )
    try:
        normalized = normalize_timeseries(raw_df, NormalizeSpec(value_field=mapping.measure))
    except NormalizeError as exc:
        raise CacheError(str(exc)) from exc

    if mapping.measure != "Cost":
        normalized["value"] = normalized["value"].astype(float) * DEFAULT_AVG_COST_PER_FTE
    else:
        normalized["value"] = normalized["value"].astype(float)
    rows = normalized.to_dict(orient="records")
    meta = build_meta(rows, source="sac")
    extra = asdict(_build_hr_cost_meta(provider_id, namespace_id, provider_name))
    save_cache(rows, meta, data_path=cache_path, extra_meta=extra)
    return normalized, {**extra, **asdict(meta)}
