from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from config import load_env_file
import os

from llm.provider import (
    LLMError,
    generate_json,
    get_last_raw_excerpt,
    get_last_raw_text,
    get_last_usage,
    model_name,
    provider_name,
)
from narrative.scenario_assistant import _build_prompts, _schema_hint, validate_and_normalize_suggestion


def main() -> int:
    load_env_file(".env", override=True)
    current_year = datetime.now(timezone.utc).year
    horizon_years = 10
    baseline_stats = {"last_value": 952000.0, "trend_12m": 49600.0, "volatility": 0.0067}
    text = "an asteroid hits the earth and erases southern America"

    def _attempt(correction_note: str = ""):
        prompts = _build_prompts(text, horizon_years, baseline_stats, correction_note=correction_note)
        return prompts, generate_json(prompts["system"], prompts["user"], schema_hint=_schema_hint())

    print(f"Provider: {provider_name()}")
    print(f"Model: {model_name()}")
    print(f"Max tokens: {os.getenv('LLM_MAX_TOKENS', '')}")
    prompts = {}
    try:
        prompts, result = _attempt()
    except LLMError as exc:
        if str(exc) == "invalid_llm_output":
            correction = (
                "CORRECT YOUR JSON: Return a single-line, valid JSON object only; "
                "no code fences, no trailing commas, no empty string items, and end after the final }."
            )
            try:
                prompts, result = _attempt(correction_note=correction)
            except LLMError as retry_exc:
                exc = retry_exc
        if isinstance(exc, LLMError):
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
        return 1

    if not isinstance(result, dict) or "params" not in result:
        print("LLM ERROR (invalid_schema)")
        print(f"Response: {result}")
        return 1

    params = result.get("params", {})
    try:
        params, consistency, warnings = validate_and_normalize_suggestion(params, horizon_years)
        if warnings:
            print("Warnings:", " | ".join(warnings))
        if consistency == "corrected":
            print("Note: parameters normalized for bounds.")
    except LLMError as exc:
        print(f"LLM ERROR ({exc})")
        return 1
    shock_year = params.get("shock_start_year")
    if shock_year is not None:
        try:
            shock_year = int(shock_year)
        except (TypeError, ValueError):
            print("LLM ERROR (invalid_shock_year)")
            print(f"Response: {result}")
            return 1
        if shock_year < current_year or shock_year > current_year + horizon_years:
            print("LLM ERROR (shock_year_out_of_range)")
            print(f"Response: {result}")
            return 1

    print("LLM OK (scenario)")
    usage = get_last_usage()
    if usage:
        print("Usage:", usage)
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
