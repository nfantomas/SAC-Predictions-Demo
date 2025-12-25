from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Dict, Iterable, Optional, Tuple

from llm.anthropic_provider import generate_json as anthropic_generate
from llm.provider import LLMError

PROMPT_PATH = Path("llm/prompts/scenario_assistant_v2.txt")


def _write_debug_log(data: Dict[str, object]) -> None:
    try:
        with open("llm_debug.log", "a", encoding="utf-8") as handle:
            handle.write(json.dumps(data, sort_keys=True) + "\n")
    except Exception:
        return


def _schema_hint() -> Dict[str, object]:
    return {
        "params": {
            "preset_base": "string or null",
            "growth_delta_pp_per_year": "float",
            "shock_start_year": "int or null",
            "shock_pct": "float",
            "shock_duration_months": "int or null",
            "drift_pp_per_year": "float",
        },
        "rationale": {
            "summary": "string (2-4 sentences)",
            "drivers": ["bullet string", "bullet string"],
            "assumptions": ["bullet string", "bullet string"],
            "confidence": "low|medium|high",
            "checks": {"text_sentiment": "upside|downside|neutral", "param_consistency": "ok|corrected"},
        },
    }


def _llm_request_preview(prompts: Dict[str, str]) -> Dict[str, object]:
    return {
        "model": os.getenv("ANTHROPIC_MODEL", "claude-opus-4-20250514"),
        "max_tokens": int(os.getenv("LLM_MAX_TOKENS", "2048")),
        "stop_sequences": [item.strip() for item in os.getenv("LLM_STOP_SEQUENCES", "").split(",") if item.strip()],
        "system": prompts.get("system", ""),
        "user": prompts.get("user", ""),
        "schema_hint": _schema_hint(),
    }

def _contains_any(text: str, keywords: Iterable[str]) -> bool:
    lowered = text.lower()
    for keyword in keywords:
        term = keyword.lower()
        if " " in term:
            if term in lowered:
                return True
        else:
            if re.search(rf"\b{re.escape(term)}\b", lowered):
                return True
    return False


def _looks_severe(text: str) -> bool:
    severe_terms = (
        "asteroid",
        "meteor",
        "catastrophe",
        "catastrophic",
        "apocalypse",
        "collapse",
        "war",
        "invasion",
        "pandemic",
        "earthquake",
        "hurricane",
        "tsunami",
        "flood",
        "firestorm",
        "nuclear",
    )
    return _contains_any(text, severe_terms)


def _classify_text_sentiment(text: str) -> str:
    upside = (
        "growth",
        "boom",
        "recovery",
        "reconciliation",
        "trade war is over",
        "trade wars is over",
        "easing tariffs",
        "ai leap",
        "productivity",
        "expansion",
        "upswing",
    )
    downside = (
        "war",
        "trade war",
        "sanctions",
        "recession",
        "crisis",
        "collapse",
        "pandemic",
        "asteroid",
        "earthquake",
    )
    if _contains_any(text, upside) and not _contains_any(text, downside):
        return "upside"
    if _contains_any(text, downside) and not _contains_any(text, upside):
        return "downside"
    return "neutral"


def _allows_cost_reduction(text: str) -> bool:
    return _contains_any(
        text,
        (
            "automation",
            "productivity",
            "efficiency",
            "headcount reduction",
            "labor saving",
        ),
    )


def validate_and_normalize_suggestion(
    params: Dict[str, object], horizon_years: int
) -> Tuple[Dict[str, object], str, list[str]]:
    corrected = False
    warnings = []
    current_year = datetime.now(timezone.utc).year
    max_year = current_year + horizon_years
    normalized = {
        "preset_base": params.get("preset_base"),
        "growth_delta_pp_per_year": float(params.get("growth_delta_pp_per_year", 0.0)),
        "shock_start_year": params.get("shock_start_year"),
        "shock_pct": float(params.get("shock_pct", 0.0)),
        "shock_duration_months": params.get("shock_duration_months"),
        "drift_pp_per_year": float(params.get("drift_pp_per_year", 0.0)),
    }

    if abs(normalized["shock_pct"]) > 1.5:
        normalized["shock_pct"] = normalized["shock_pct"] / 100.0
        corrected = True
        warnings.append("Normalized shock_pct from percent to fraction.")

    if normalized["shock_pct"] < -0.9 or normalized["shock_pct"] > 1.0:
        raise LLMError("shock_pct_out_of_bounds")

    if normalized["growth_delta_pp_per_year"] < -0.5 or normalized["growth_delta_pp_per_year"] > 0.5:
        raise LLMError("growth_delta_out_of_bounds")

    if normalized["drift_pp_per_year"] < -0.5 or normalized["drift_pp_per_year"] > 0.5:
        raise LLMError("drift_out_of_bounds")

    shock_year = normalized["shock_start_year"]
    shock_year_int = None
    if shock_year is not None:
        try:
            shock_year_int = int(shock_year)
        except (TypeError, ValueError):
            shock_year_int = None
    if shock_year_int is not None and (shock_year_int < current_year or shock_year_int > max_year):
        normalized["shock_start_year"] = None
        corrected = True
    else:
        normalized["shock_start_year"] = shock_year_int

    duration = normalized["shock_duration_months"]
    if duration is not None:
        try:
            duration = int(duration)
        except (TypeError, ValueError):
            duration = None
    if duration is not None and duration < 0:
        raise LLMError("shock_duration_out_of_bounds")
    max_duration = horizon_years * 12
    if duration is not None and duration > max_duration:
        duration = max_duration
        corrected = True
    normalized["shock_duration_months"] = duration

    return normalized, "corrected" if corrected else "ok", warnings


def _is_uninformative_output(params: Dict[str, object]) -> bool:
    return (
        params.get("growth_delta_pp_per_year") in (0, 0.0)
        and params.get("shock_start_year") in (None, 0)
        and params.get("shock_pct") in (0, 0.0)
        and params.get("shock_duration_months") in (None, 0, 12)
        and params.get("drift_pp_per_year") in (0, 0.0)
    )


def _load_prompt_template() -> str:
    try:
        return PROMPT_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _template_suggestion(text: str, horizon_years: int) -> Dict[str, object]:
    lowered = text.lower()
    suggestion = {
        "preset_base": None,
        "growth_delta_pp_per_year": 0.0,
        "shock_start_year": None,
        "shock_pct": 0.0,
        "shock_duration_months": 12,
        "drift_pp_per_year": 0.0,
    }
    rationale = []
    warnings = []

    if _looks_severe(lowered):
        shock_year = datetime.now(timezone.utc).year
        suggestion.update(
            {
                "growth_delta_pp_per_year": -0.08,
                "shock_start_year": shock_year,
                "shock_pct": -0.25,
                "shock_duration_months": 24,
                "drift_pp_per_year": -0.02,
            }
        )
        rationale.append("Severe disruption implies an immediate shock and slower growth.")
        warnings.append("Scenario reflects a catastrophic event; treat as illustrative.")

    relief = False
    if (
        "trade war is over" in lowered
        or "trade wars is over" in lowered
        or "reconciliation" in lowered
        or "easing tariffs" in lowered
        or "de-escalation" in lowered
    ):
        suggestion.update(
            {
                "preset_base": "growth_upside",
                "growth_delta_pp_per_year": 0.02,
                "shock_start_year": None,
                "shock_pct": 0.0,
                "shock_duration_months": 0,
            }
        )
        rationale.append("Trade-war relief suggests improved growth and no shock.")
        relief = True

    if ("trade war" in lowered or "trade-war" in lowered) and not relief:
        suggestion.update(
            {
                "preset_base": "trade_war_downside",
                "growth_delta_pp_per_year": -0.03,
                "shock_start_year": None,
                "shock_pct": -0.08,
                "shock_duration_months": 12,
            }
        )
        rationale.append("Trade war implies a demand shock and slower growth.")

    if "aging" in lowered or "demographic" in lowered:
        suggestion.update(
            {
                "preset_base": "aging_pressure",
                "drift_pp_per_year": -0.02,
            }
        )
        rationale.append("Aging workforce suggests gradual negative drift.")

    if "hiring freeze" in lowered:
        suggestion.update(
            {
                "growth_delta_pp_per_year": -0.05,
                "shock_pct": -0.05,
                "shock_duration_months": 12,
            }
        )
        rationale.append("Hiring freeze reduces growth and creates a short-term dip.")

    if "inflation" in lowered:
        suggestion.update(
            {
                "growth_delta_pp_per_year": 0.02,
            }
        )
        rationale.append("Inflation can raise cost growth assumptions.")

    if not rationale:
        rationale.append("No strong keywords detected; returning baseline parameters.")

    suggestion["shock_pct"] = max(-0.9, min(1.0, suggestion["shock_pct"]))
    suggestion["growth_delta_pp_per_year"] = max(-0.5, min(0.5, suggestion["growth_delta_pp_per_year"]))

    return {
        "mode": "template",
        "params": suggestion,
        "rationale": {
            "summary": " ".join(rationale),
            "drivers": rationale[:2] if rationale else [],
            "assumptions": ["Template rule-based mapping; no LLM used."],
            "confidence": "low" if not rationale else "medium",
            "checks": {
                "text_sentiment": _classify_text_sentiment(lowered),
                "param_consistency": "ok",
            },
        },
        "warnings": warnings,
        "fallback_reason": "template",
    }


def _build_prompts(
    indications_text: str,
    horizon_years: int,
    baseline_stats: Dict[str, float],
    correction_note: str = "",
) -> Dict[str, str]:
    current_year = datetime.now(timezone.utc).year
    max_year = current_year + horizon_years
    template = _load_prompt_template()
    if not template:
        template = "Return JSON only. {schema}\nUser text: {indications_text}\n"
    user_prompt = template.format(
        schema=_schema_hint(),
        indications_text=indications_text,
        horizon_years=horizon_years,
        baseline_stats=baseline_stats,
        current_year=current_year,
        max_year=max_year,
        correction_note=correction_note.strip(),
    )
    system_prompt = "Return JSON only. Do not include markdown, code fences, or commentary."
    return {"system": system_prompt, "user": user_prompt}


def suggest_scenario(
    indications_text: str,
    horizon_years: int,
    baseline_stats: Dict[str, float],
    use_llm: bool = False,
) -> Dict[str, object]:
    prompts = _build_prompts(indications_text, horizon_years, baseline_stats)
    sentiment = _classify_text_sentiment(indications_text.lower())

    if not os.getenv("ANTHROPIC_API_KEY"):
        return {
            "mode": "llm_error",
            "error": "missing_llm_key",
            "llm_request": _llm_request_preview(prompts),
            "prompts": prompts,
        }

    def _attempt(correction_note: str = "") -> Dict[str, object]:
        attempt_prompts = _build_prompts(
            indications_text, horizon_years, baseline_stats, correction_note=correction_note
        )
        output = anthropic_generate(attempt_prompts["system"], attempt_prompts["user"], _schema_hint())
        if not isinstance(output, dict) or "params" not in output or "rationale" not in output:
            raise LLMError("invalid_llm_output")
        params, consistency, warnings = validate_and_normalize_suggestion(
            output.get("params", {}), horizon_years
        )
        rationale = output.get("rationale") or {}
        summary = str(rationale.get("summary", "")).strip()
        drivers = rationale.get("drivers") if isinstance(rationale.get("drivers"), list) else []
        assumptions = (
            rationale.get("assumptions") if isinstance(rationale.get("assumptions"), list) else []
        )
        confidence = rationale.get("confidence", "medium")
        checks = rationale.get("checks", {})
        rationale_text = " ".join([summary] + drivers + assumptions).lower()
        if sentiment == "upside" and params["growth_delta_pp_per_year"] < 0:
            if not _allows_cost_reduction(rationale_text):
                raise LLMError("llm_inconsistent")
        if sentiment == "downside" and params["growth_delta_pp_per_year"] > 0:
            if not _allows_cost_reduction(rationale_text):
                raise LLMError("llm_inconsistent")

        checks = {
            "text_sentiment": sentiment,
            "param_consistency": consistency if consistency == "corrected" else "ok",
        }
        output = {
            "params": params,
            "rationale": {
                "summary": summary or "LLM suggestion based on scenario text.",
                "drivers": drivers or ["LLM-derived macro drivers."],
                "assumptions": assumptions or ["LLM assumed standard macro-to-HR cost mapping."],
                "confidence": confidence if confidence in ("low", "medium", "high") else "medium",
                "checks": checks,
            },
        }
        if warnings:
            output["warnings"] = warnings
        if _looks_severe(indications_text.lower()) and _is_uninformative_output(params):
            raise LLMError("llm_uninformative")
        output["llm_request"] = _llm_request_preview(attempt_prompts)
        output["prompts"] = attempt_prompts
        return output

    try:
        output = _attempt()
        result = {
            "mode": "llm",
            "params": output["params"],
            "rationale": output["rationale"],
            "warnings": output.get("warnings", []),
            "llm_request": output["llm_request"],
            "prompts": output["prompts"],
            "llm_model": os.getenv("ANTHROPIC_MODEL", ""),
        }
        _write_debug_log({"mode": "llm", "prompts": output["prompts"], "suggestion": output})
        return result
    except Exception as exc:
        reason = str(exc)
        correction = None
        correction_label = None
        if "llm_inconsistent" in reason:
            correction = (
                "CORRECT YOUR JSON: Your parameters contradict the user intent. "
                "Ensure growth_delta_pp_per_year matches the text sentiment, "
                "or clearly explain automation-driven cost reduction."
            )
            correction_label = "LLM corrected for consistency."
        elif "invalid_llm_output" in reason:
            correction = (
                "CORRECT YOUR JSON: Your output was invalid or truncated. "
                "Return a single-line, valid JSON object only; no code fences, no trailing commas, "
                "no empty string items, no extra keys, and end immediately after the final }. "
                "Keep summary/drivers/assumptions very short."
            )
            correction_label = "LLM corrected for JSON validity."

        if correction:
            try:
                output = _attempt(correction_note=correction)
                result = {
                    "mode": "llm",
                    "params": output["params"],
                    "rationale": output["rationale"],
                    "warnings": output.get("warnings", []) + [correction_label],
                    "llm_request": output["llm_request"],
                    "prompts": output["prompts"],
                    "llm_model": os.getenv("ANTHROPIC_MODEL", ""),
                }
                _write_debug_log({"mode": "llm", "prompts": output["prompts"], "suggestion": output})
                return result
            except Exception as retry_exc:
                reason = str(retry_exc)

        if "invalid_llm_output" in reason:
            reason = "invalid_llm_output"
        elif "llm_timeout" in reason:
            reason = "llm_timeout"
        elif "llm_uninformative" in reason:
            reason = "llm_uninformative"
        elif "llm_inconsistent" in reason:
            reason = "llm_inconsistent"
        _write_debug_log({"mode": "llm_error", "prompts": prompts, "error": reason})
        return {
            "mode": "llm_error",
            "error": reason,
            "llm_request": _llm_request_preview(prompts),
            "prompts": prompts,
        }
