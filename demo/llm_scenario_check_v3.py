from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

from config import load_env_file
from llm.provider import (
    LLMError,
    generate_json,
    get_last_raw_excerpt,
    get_last_raw_text,
    get_last_usage,
    model_name,
    provider_name,
)
from scenarios.schema import ScenarioParamsV3


PROMPT_PATH = Path("llm/prompts/scenario_assistant_v3.txt")
SCHEMA_PATH = Path("llm/schema/scenario_suggestion_v3.json")


def _load_prompt_template() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def _schema_hint() -> Dict[str, object]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _build_prompts(user_text: str, horizon_years: int, baseline_stats: Dict[str, object]) -> Dict[str, str]:
    tmpl = _load_prompt_template()
    system = tmpl.format(indications_text=user_text, horizon_years=horizon_years, baseline_stats=baseline_stats)
    return {"system": system, "user": ""}


def _report_error(exc: LLMError) -> None:
    print(f"LLM ERROR ({exc})")
    raw_full = get_last_raw_text()
    if raw_full:
        output_path = Path("data/llm_last_raw_response.txt")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(raw_full, encoding="utf-8")
        print(f"Raw response saved to: {output_path}")
        print("Raw response:")
        print(raw_full)
    else:
        raw = get_last_raw_excerpt()
        if raw:
            print("Raw response excerpt:")
            print(raw)
    usage = get_last_usage()
    if usage:
        print("Usage:", usage)


def main() -> int:
    load_env_file(".env", override=True)
    current_year = datetime.now(timezone.utc).year
    horizon_years = 10
    baseline_stats = {"last_value": 10_000_000.0, "trend_12m": 120_000.0, "volatility": 0.01}
    prompts = _build_prompts("Suggest a cautious inflation shock scenario.", horizon_years, baseline_stats)

    print(f"Provider: {provider_name()}")
    print(f"Model: {model_name()}")
    try:
        result = generate_json(prompts["system"], prompts["user"], schema_hint=_schema_hint())
    except LLMError as exc:
        _report_error(exc)
        return 1

    if not isinstance(result, dict) or "params" not in result:
        print("LLM ERROR (invalid_schema)")
        print(f"Response: {result}")
        return 1

    params = result.get("params", {})
    try:
        # basic shape check to ensure required keys exist
        ScenarioParamsV3(**{**params, "impact_mode": params.get("impact_mode", "level")})
    except Exception:
        print("LLM ERROR (invalid_params)")
        print(f"Response: {result}")
        return 1

    print("LLM OK (scenario v3)")
    usage = get_last_usage()
    if usage:
        print("Usage:", usage)
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
