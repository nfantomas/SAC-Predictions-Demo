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


_ALLOWED_MEASURES = {"SignedData", "Cost"}


def _load_filters() -> Dict[str, str]:
    raw = os.getenv("HR_COST_FILTERS_JSON", "").strip()
    if not raw:
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
    measure = os.getenv("HR_COST_MEASURE", "SignedData").strip()
    if measure not in _ALLOWED_MEASURES:
        raise MetricMappingError(
            f"Unsupported HR_COST_MEASURE '{measure}'. Allowed: {', '.join(sorted(_ALLOWED_MEASURES))}."
        )
    currency = os.getenv("HR_COST_CURRENCY", "EUR").strip() or "EUR"
    grain = os.getenv("HR_COST_GRAIN", "month").strip() or "month"
    filters = _load_filters()
    calculation = "direct_measure" if measure == "Cost" else "fte_times_avg_cost"
    return MetricMapping(
        metric_name="hr_cost",
        measure=measure,
        currency=currency,
        grain=grain,
        unit="monthly_cost",
        filters=filters,
        calculation=calculation,
    )
