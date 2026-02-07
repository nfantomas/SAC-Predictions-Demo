from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict

from llm.intent_schema import ScenarioIntent, intent_schema_json
from llm.provider import (
    LLMError,
    generate_json,
    get_last_raw_excerpt,
    get_last_raw_text,
    get_last_usage,
    model_name,
    provider_name,
)


PROMPT_PATH = Path("llm/prompts/intent_interpreter.md")
_PCT_RE = re.compile(r"(-?\d+(?:\.\d+)?)\s*%")


def _load_prompt_template() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def _strip_json_fences(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.lstrip("`")
        cleaned = cleaned.replace("json", "", 1).strip()
    if cleaned.endswith("```"):
        cleaned = cleaned.rstrip("`").strip()
    return cleaned


def _default_start(baseline_stats: Dict[str, object]) -> str:
    last_date = str(baseline_stats.get("last_date") or baseline_stats.get("last_month") or "")
    if len(last_date) >= 7:
        year = last_date[:4]
        if year.isdigit():
            return f"{int(year) + 1:04d}-01"
    return "2028-01"


def _fallback_intent(baseline_stats: Dict[str, object], question: str) -> ScenarioIntent:
    return ScenarioIntent(
        schema_version="intent_v1",
        intent_type="other",
        driver="auto",
        direction="unknown",
        magnitude={"type": "none", "value": None},
        timing={"start": _default_start(baseline_stats), "duration_months": None, "ramp_months": 3},
        constraints=[],
        entities={"regions": None, "population": "global"},
        severity="operational",
        confidence="low",
        need_clarification=True,
        clarifying_question=question,
    )


def _build_system_prompt(user_text: str, baseline_stats: Dict[str, object]) -> str:
    template = _load_prompt_template()
    return template.replace("{user_text}", str(user_text)).replace("{baseline_stats}", str(baseline_stats))


def _parse_payload(payload: Any) -> ScenarioIntent:
    if isinstance(payload, ScenarioIntent):
        return payload
    if isinstance(payload, str):
        cleaned = _strip_json_fences(payload)
        payload = json.loads(cleaned)
    return ScenarioIntent.model_validate(payload)


def _call_llm(system_prompt: str, user_prompt: str) -> Dict[str, object]:
    return generate_json(system_prompt, user_prompt, schema_hint=intent_schema_json())


def _extract_pct(text: str) -> float | None:
    m = _PCT_RE.search(text)
    if not m:
        return None
    val = float(m.group(1))
    return val / 100.0


def _apply_heuristics(intent: ScenarioIntent, user_text: str) -> ScenarioIntent:
    text = (user_text or "").lower()
    pct = _extract_pct(text)
    has_no_layoffs = ("no layoffs" in text) or ("no layoff" in text)
    cost_words = any(k in text for k in ("cost reduction", "reduce cost", "reduce costs", "cut costs", "costs by"))
    keep_cost_flat = any(k in text for k in ("keep costs flat", "keep costs at current level", "keep costs at current levels"))
    if keep_cost_flat:
        data = intent.model_dump()
        data["intent_type"] = "constraint"
        data["driver"] = "cost"
        data["direction"] = "hold"
        data["magnitude"] = {"type": "yoy_cap", "value": 0.0}
        constraints = set(data.get("constraints", []))
        constraints.add("keep_cost_flat")
        data["constraints"] = sorted(constraints)
        return ScenarioIntent.model_validate(data)

    if pct is not None and cost_words:
        data = intent.model_dump()
        data["intent_type"] = "target"
        data["driver"] = "cost_target"
        if pct > 0 and any(k in text for k in ("reduce", "reduction", "cut", "decrease", "lower")):
            pct = -pct
        data["direction"] = "decrease" if pct < 0 else "increase"
        data["magnitude"] = {"type": "pct", "value": pct}
        constraints = set(data.get("constraints", []))
        if has_no_layoffs:
            constraints.add("no_layoffs")
        data["constraints"] = sorted(constraints)
        return ScenarioIntent.model_validate(data)

    if has_no_layoffs:
        data = intent.model_dump()
        constraints = set(data.get("constraints", []))
        constraints.add("no_layoffs")
        data["constraints"] = sorted(constraints)
        return ScenarioIntent.model_validate(data)

    return intent


def interpret_intent(
    user_text: str,
    baseline_stats: Dict[str, object],
    *,
    user_prompt: str | None = None,
) -> Dict[str, object]:
    system_prompt = _build_system_prompt(user_text, baseline_stats)
    user_prompt = user_prompt or "Return ScenarioIntent JSON only."
    try:
        response = _call_llm(system_prompt, user_prompt)
        intent = _apply_heuristics(_parse_payload(response), user_text)
        return {
            "provider": provider_name(),
            "model": model_name(),
            "prompts": {"system": system_prompt, "user": user_prompt},
            "intent": intent.model_dump(),
            "usage": get_last_usage(),
            "raw_text": get_last_raw_text(),
            "raw_excerpt": get_last_raw_excerpt(),
            "repaired": False,
        }
    except Exception:
        pass

    # Repair attempt
    repair_prompt = (
        "Return ONLY valid ScenarioIntent JSON. Do not include markdown or extra text."
    )
    try:
        response = _call_llm(system_prompt, repair_prompt)
        intent = _apply_heuristics(_parse_payload(response), user_text)
        return {
            "provider": provider_name(),
            "model": model_name(),
            "prompts": {"system": system_prompt, "user": repair_prompt},
            "intent": intent.model_dump(),
            "usage": get_last_usage(),
            "raw_text": get_last_raw_text(),
            "raw_excerpt": get_last_raw_excerpt(),
            "repaired": True,
        }
    except Exception:
        intent = _fallback_intent(
            baseline_stats,
            "Could you clarify whether this is a temporary shock or a permanent change?",
        )
        intent = _apply_heuristics(intent, user_text)
        return {
            "provider": provider_name(),
            "model": model_name(),
            "prompts": {"system": system_prompt, "user": repair_prompt},
            "intent": intent.model_dump(),
            "usage": get_last_usage(),
            "raw_text": get_last_raw_text(),
            "raw_excerpt": get_last_raw_excerpt(),
            "repaired": True,
            "fallback": True,
        }
