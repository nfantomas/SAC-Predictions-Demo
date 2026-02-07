from __future__ import annotations

from dataclasses import replace
from typing import List, Tuple

from scenarios.schema import ScenarioParamsV3


_PERCENT_FIELDS = (
    "impact_magnitude",
    "growth_delta_pp_per_year",
    "drift_pp_per_year",
    "event_growth_delta_pp_per_year",
    "post_event_growth_pp_per_year",
    "fte_delta_pct",
    "cost_target_pct",
)


def _normalize_value(value: float | None) -> tuple[float | None, bool]:
    if value is None:
        return value, False
    if abs(value) > 1.5:
        return value / 100.0, True
    return value, False


def normalize_params(params: ScenarioParamsV3) -> Tuple[ScenarioParamsV3, List[str]]:
    warnings: List[str] = []
    updates = {}
    for field in _PERCENT_FIELDS:
        raw = getattr(params, field)
        normalized, changed = _normalize_value(raw)
        if changed:
            updates[field] = normalized
            warnings.append(f"Normalized {field} {raw} -> {normalized} assuming percent units.")
    if updates:
        params = replace(params, **updates)
    return params, warnings
