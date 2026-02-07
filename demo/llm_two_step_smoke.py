from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from llm.intent_interpreter import interpret_intent
from llm.intent_schema import ScenarioIntent
from llm.validate_v3 import ValidateContext, validate_and_sanitize_result
from scenarios.compiler_v3 import compile_intent
from scenarios.v3 import DriverContext, apply_scenario_v3_simple
from ui.warnings import summarize_warnings


def _baseline(months: int = 120, start: str = "2028-01-01") -> pd.DataFrame:
    dates = pd.date_range(start, periods=months, freq="MS")
    return pd.DataFrame({"date": dates.date.astype(str), "yhat": [10_000_000.0] * months})


def main() -> None:
    parser = argparse.ArgumentParser(description="Two-step assistant smoke test (real LLM).")
    parser.add_argument("--prompts", required=True, help="Path to sample_prompts.json")
    parser.add_argument("--limit", type=int, default=5, help="Number of prompts to run")
    args = parser.parse_args()

    prompts = json.loads(Path(args.prompts).read_text())
    if not isinstance(prompts, list):
        raise ValueError("prompts file must contain a list.")

    base = _baseline()
    t0_start = "2028-01"
    ctx = DriverContext(alpha=2_000_000, beta0=10_000)

    for item in prompts[: args.limit]:
        prompt = item.get("prompt", "")
        print(f"\nPrompt: {prompt}")
        try:
            intent_result = interpret_intent(prompt, {"last_date": "2027-12"})
            intent = ScenarioIntent.model_validate(intent_result["intent"])
        except Exception as exc:
            print(f"Intent parse failed: {exc}")
            continue

        compiled = compile_intent(intent, t0_start=t0_start, horizon_months=len(base))
        print(f"Intent: {intent.intent_type} | Severity: {intent.severity}")
        print(f"Compiled params: {compiled.params_v3}")

        if compiled.needs_clarification:
            print(f"Clarify: {compiled.clarifying_question}")
            continue

        params = compiled.params_v3
        _, _, result = validate_and_sanitize_result(
            params.__dict__,
            ctx=ValidateContext(horizon_months=len(base), severity=intent.severity),
        )
        warn_msgs = [w.message for w in result.warnings]
        clamp_msgs = [c.message for c in result.clamps]
        summary, _ = summarize_warnings(warn_msgs, clamp_msgs, [])
        print(f"Warning summary count: {len(summary)}")

        if result.errors:
            print("Applied: false (validation errors)")
            for issue in result.errors:
                print(f"- {issue.message}")
            continue

        scenario = apply_scenario_v3_simple(base, params, context=ctx, horizon_months=len(base))
        applied = scenario["yhat"].notna().all() and (scenario["yhat"] >= 0).all()
        print(f"Applied: {str(applied).lower()}")


if __name__ == "__main__":
    main()
