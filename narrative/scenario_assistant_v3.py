from __future__ import annotations

from typing import Dict, List, Tuple

from scenarios.presets_v3 import PRESETS_V3
from scenarios.schema import ScenarioParamsV3


def _preset_keywords() -> Dict[str, Tuple[str, ...]]:
    return {
        "hiring_freeze": ("freeze", "hiring freeze", "stop hiring"),
        "convert_it_contractors": ("contractor", "convert", "employee conversion", "it contractor"),
        "inflation_shock": ("inflation", "price", "caps", "role cap", "country a", "country b"),
        "outsource_120_uk_cz": ("outsource", "offshore", "shift to"),
        "reduce_cost_10pct": ("reduce cost", "cut cost", "10%", "ten percent"),
    }


def _match_preset(user_text: str) -> str:
    text = (user_text or "").lower()
    for preset_id, keywords in _preset_keywords().items():
        if any(k in text for k in keywords):
            return preset_id
    return "freeze_hiring"


def suggest_preset_v3(user_text: str) -> Dict[str, object]:
    preset_id = _match_preset(user_text)
    preset = PRESETS_V3[preset_id]
    params: ScenarioParamsV3 = preset.params
    rationale = _build_rationale(preset_id, preset)
    return {
        "preset_id": preset_id,
        "params": params,
        "overrides": {},
        "rationale": rationale,
    }


def _build_rationale(preset_id: str, preset) -> Dict[str, object]:
    summaries = {
        "freeze_hiring": "Pause net hiring to stabilize costs and allow mild attrition.",
        "convert_it_contractors": "Convert contractors to employees to lower per-FTE cost while growing headcount slightly.",
        "inflation_ab_role_caps": "Model different inflation levels in A/B and cap FTE growth to zero during the shock.",
        "outsource_120_fte": "Shift 120 FTE to a cheaper region, reducing variable cost while keeping FTE constant.",
        "reduce_cost_10pct": "Meet a 10% cost target by translating the gap into FTE cuts by seniority.",
    }
    assumptions: List[str] = []
    if preset_id == "inflation_ab_role_caps":
        assumptions.append("Using assumed segment weights if A/B not present in data.")
    if preset_id == "reduce_cost_10pct":
        assumptions.append("Seniority distribution: Junior 50%, Mid 35%, Senior 15%.")
    if preset_id == "convert_it_contractors":
        assumptions.append("Beta multiplier reflects contractor premium removal.")
    return {
        "summary": summaries.get(preset_id, preset.description),
        "assumptions": assumptions or ["Defaults applied; adjust as needed."],
    }


__all__ = ["suggest_preset_v3"]
