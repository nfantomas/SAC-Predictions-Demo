from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable, Dict, List

from llm.provider import generate_json


_PROMPT_PATH = Path("evals/grader_prompt.md")
_TAG_ALLOWLIST = {
    "driver_selection",
    "units",
    "timing",
    "fixed_variable_logic",
    "utilization_math",
    "rate_math",
    "capacity_logic",
    "safety_extremes",
    "clarity",
    "missing_assumptions",
}

_DEFAULT_GRADE = {
    "score": 1,
    "reasoning": "Fallback grader used because strict JSON grading could not be parsed reliably.",
    "tags": ["clarity"],
    "suggested_fix": [
        "Return strict JSON with valid score, tags, and concise reasoning.",
    ],
}


def _schema_hint() -> Dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "score": {"type": "integer", "minimum": 0, "maximum": 3},
            "reasoning": {"type": "string"},
            "tags": {"type": "array", "items": {"type": "string"}},
            "suggested_fix": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["score", "reasoning", "tags", "suggested_fix"],
    }


def _load_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8").strip()


def _default_llm_call(system_prompt: str, user_prompt: str) -> Dict[str, Any]:
    return generate_json(system_prompt, user_prompt, schema_hint=_schema_hint())


def _strip_code_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.IGNORECASE)
        stripped = re.sub(r"\s*```$", "", stripped)
    return stripped.strip()


def _parse_json_like(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        raise ValueError("Grader output is not a dict/string.")

    text = _strip_code_fences(raw)
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        repaired = text[start : end + 1]
        parsed = json.loads(repaired)
        if isinstance(parsed, dict):
            return parsed
    raise ValueError("Unable to parse grader JSON.")


def _trim_reasoning(reasoning: str, max_sentences: int = 8) -> str:
    chunks = [x.strip() for x in re.split(r"(?<=[.!?])\s+", reasoning.strip()) if x.strip()]
    if len(chunks) <= max_sentences:
        return " ".join(chunks).strip() or "No reasoning provided."
    return " ".join(chunks[:max_sentences]).strip()


def _normalize_grade(parsed: Dict[str, Any]) -> Dict[str, Any]:
    score_raw = parsed.get("score")
    try:
        score = int(score_raw)
    except (TypeError, ValueError):
        score = _DEFAULT_GRADE["score"]
    score = max(0, min(3, score))

    reasoning_raw = parsed.get("reasoning")
    reasoning = str(reasoning_raw).strip() if isinstance(reasoning_raw, str) else ""
    reasoning = _trim_reasoning(reasoning or _DEFAULT_GRADE["reasoning"])

    tags_raw = parsed.get("tags")
    tags: List[str] = []
    if isinstance(tags_raw, list):
        for tag in tags_raw:
            if isinstance(tag, str):
                clean = tag.strip()
                if clean in _TAG_ALLOWLIST and clean not in tags:
                    tags.append(clean)
    if not tags:
        tags = list(_DEFAULT_GRADE["tags"])

    fixes_raw = parsed.get("suggested_fix")
    fixes: List[str] = []
    if isinstance(fixes_raw, list):
        for item in fixes_raw:
            if isinstance(item, str) and item.strip():
                fixes.append(item.strip())
    elif isinstance(fixes_raw, str) and fixes_raw.strip():
        fixes.append(fixes_raw.strip())
    if not fixes:
        fixes = list(_DEFAULT_GRADE["suggested_fix"])
    fixes = fixes[:2]

    return {
        "score": score,
        "reasoning": reasoning,
        "tags": tags,
        "suggested_fix": fixes,
    }


def grade_answer(
    *,
    question: str,
    expected_answer: str,
    model_answer: Dict[str, Any],
    llm_call: Callable[[str, str], Any] | None = None,
    max_retries: int = 2,
) -> Dict[str, Any]:
    """
    Grade one model answer with the LLM rubric and return strict normalized JSON.
    """
    caller = llm_call or _default_llm_call
    system_prompt = _load_prompt()
    payload = {
        "question": question,
        "expected_answer": expected_answer,
        "model_answer": model_answer,
    }
    user_prompt = json.dumps(payload, ensure_ascii=True)

    last_error = ""
    for attempt in range(max(1, max_retries + 1)):
        raw = caller(system_prompt, user_prompt)
        try:
            parsed = _parse_json_like(raw)
            return _normalize_grade(parsed)
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            # Make retry deterministic and explicit: ask for strict JSON only.
            user_prompt = (
                f"{json.dumps(payload, ensure_ascii=True)}\n"
                f"Previous output could not be parsed: {last_error}\n"
                "Return strict JSON only matching the schema."
            )
            continue

    fallback = dict(_DEFAULT_GRADE)
    fallback["reasoning"] = f"{_DEFAULT_GRADE['reasoning']} Last parser error: {last_error or 'unknown'}"
    return fallback

