import json
import os
from dataclasses import dataclass
from typing import Dict

from sac_connector.timeseries import DEFAULT_SLICE


class MetricMappingError(ValueError):
    pass


@dataclass(frozen=True)
class MetricMapping:
    metric_name: str
    measure: str
    currency: str
    grain: str
    unit: str
    filters: Dict[str, str]
    calculation: str
    output_mode: str


_ALLOWED_MEASURES = {"SignedData", "Cost"}
_ALLOWED_OUTPUT_MODES = {"cost", "fte"}
_DEFAULT_COST_FILTERS = {"Version": "public.Forecast", "DataSource": "General"}


def _load_output_mode() -> str:
    raw = os.getenv("HR_SERIES_MODE", "cost").strip().lower() or "cost"
    if raw not in _ALLOWED_OUTPUT_MODES:
        raise MetricMappingError(
            f"Unsupported HR_SERIES_MODE '{raw}'. Allowed: {', '.join(sorted(_ALLOWED_OUTPUT_MODES))}."
        )
    return raw


def _load_filters(output_mode: str) -> Dict[str, str]:
    raw = os.getenv("HR_COST_FILTERS_JSON", "").strip()
    if not raw:
        if output_mode == "cost":
            return dict(_DEFAULT_COST_FILTERS)
        return dict(DEFAULT_SLICE.filters)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise MetricMappingError("HR_COST_FILTERS_JSON must be valid JSON.") from exc
    if not isinstance(parsed, dict) or not parsed:
        raise MetricMappingError("HR_COST_FILTERS_JSON must be a non-empty JSON object.")
    filters = {}
    for key, value in parsed.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise MetricMappingError("HR_COST_FILTERS_JSON must map strings to strings.")
        filters[key] = value
    return filters


def get_metric_mapping() -> MetricMapping:
    output_mode = _load_output_mode()
    default_measure = "Cost" if output_mode == "cost" else "SignedData"
    measure = os.getenv("HR_COST_MEASURE", default_measure).strip()
    if measure not in _ALLOWED_MEASURES:
        raise MetricMappingError(
            f"Unsupported HR_COST_MEASURE '{measure}'. Allowed: {', '.join(sorted(_ALLOWED_MEASURES))}."
        )
    if output_mode == "fte" and measure == "Cost":
        raise MetricMappingError("HR_SERIES_MODE=fte requires HR_COST_MEASURE=SignedData.")
    currency = ""
    if output_mode == "cost":
        currency = os.getenv("HR_COST_CURRENCY", "EUR").strip() or "EUR"
    grain = os.getenv("HR_COST_GRAIN", "month").strip() or "month"
    filters = _load_filters(output_mode)
    if output_mode == "fte":
        calculation = "raw_fte"
    else:
        calculation = "direct_measure" if measure == "Cost" else "fte_times_avg_cost"
    metric_name = "fte" if output_mode == "fte" else "hr_cost"
    unit = "fte" if output_mode == "fte" else "monthly_cost"
    return MetricMapping(
        metric_name=metric_name,
        measure=measure,
        currency=currency,
        grain=grain,
        unit=unit,
        filters=filters,
        calculation=calculation,
        output_mode=output_mode,
    )
