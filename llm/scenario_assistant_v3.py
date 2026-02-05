from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

from llm.provider import (
    LLMError,
    generate_json,
    get_last_raw_excerpt,
    get_last_raw_text,
    get_last_usage,
    model_name,
    provider_name,
)

PROMPT_PATH = Path("llm/prompts/scenario_assistant_v3.txt")
SCHEMA_PATH = Path("llm/schema/scenario_suggestion_v3.json")


def _load_prompt_template() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def schema_hint() -> Dict[str, object]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def build_prompts(user_text: str, horizon_years: int, baseline_stats: Dict[str, object]) -> Dict[str, str]:
    tmpl = _load_prompt_template()
    system = (
        tmpl.replace("{indications_text}", str(user_text))
        .replace("{horizon_years}", str(horizon_years))
        .replace("{baseline_stats}", str(baseline_stats))
    )
    user = user_text or "Generate a scenario JSON based on the system prompt."
    return {"system": system, "user": user}


def request_suggestion(user_text: str, horizon_years: int, baseline_stats: Dict[str, object]) -> Dict[str, object]:
    prompts = build_prompts(user_text, horizon_years, baseline_stats)
    return {
        "provider": provider_name(),
        "model": model_name(),
        "prompts": prompts,
        "response": generate_json(prompts["system"], prompts["user"], schema_hint=schema_hint()),
        "usage": get_last_usage(),
        "raw_text": get_last_raw_text(),
        "raw_excerpt": get_last_raw_excerpt(),
    }
