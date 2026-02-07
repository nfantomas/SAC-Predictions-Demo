from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Sequence

from config import DEFAULT_ASSUMPTIONS
from evals.assistant_v3_eval import EvalCase, load_eval_cases, select_eval_cases
from llm.provider import LLMError, has_llm_key, list_models, model_name, provider_name
from llm.scenario_assistant_v3 import request_suggestion
from llm.validation_result import summarize_warnings
from ui.assistant_v3_pipeline import build_driver_context, parse_suggestion, resolve_driver_and_params


def _preflight_llm() -> tuple[bool, str]:
    if not has_llm_key():
        return False, "Missing LLM API key."
    try:
        models = list_models()
    except LLMError as exc:
        return False, str(exc)
    model = model_name()
    if model not in models:
        return False, f"Model '{model}' not available for provider '{provider_name()}'."
    return True, f"LLM OK ({provider_name()}, model={model})"


def _extract_multiplier(suggestion: Dict[str, Any]) -> float | None:
    rationale = suggestion.get("rationale") or {}
    if not isinstance(rationale, dict):
        return None
    sanity = rationale.get("sanity_checks") or {}
    if not isinstance(sanity, dict):
        return None
    raw = sanity.get("ten_year_multiplier_estimate")
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _key_params(params_obj: Any) -> Dict[str, Any]:
    if hasattr(params_obj, "__dict__"):
        raw = dict(params_obj.__dict__)
    else:
        raw = dict(params_obj or {})
    keys = (
        "driver",
        "lag_months",
        "onset_duration_months",
        "impact_mode",
        "impact_magnitude",
        "growth_delta_pp_per_year",
        "drift_pp_per_year",
        "fte_delta_pct",
        "fte_delta_abs",
        "beta_multiplier",
        "cost_target_pct",
    )
    return {k: raw.get(k) for k in keys}


def run_evals(
    cases: Sequence[EvalCase],
    n: int = 3,
    horizon_years: int = 10,
    horizon_months: int = 120,
    observed_t0_cost: float = DEFAULT_ASSUMPTIONS.t0_cost,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for case in cases:
        for run_idx in range(1, n + 1):
            started = time.perf_counter()
            error = ""
            hard_fail = False
            suggested_driver = "unknown"
            warning_summary_count = 0
            params_out: Dict[str, Any] = {}
            ten_year_multiplier = None
            try:
                baseline_stats = {
                    "last_value": observed_t0_cost,
                    "trend_12m": observed_t0_cost * 0.06 / 12,
                    "volatility": 0.01,
                }
                llm_out = request_suggestion(case.question, horizon_years, baseline_stats)
                suggestion = llm_out.get("response") if isinstance(llm_out, dict) else llm_out
                if isinstance(suggestion, str):
                    suggestion = parse_suggestion(suggestion)
                if not isinstance(suggestion, dict):
                    raise ValueError("Invalid suggestion payload.")
                ten_year_multiplier = _extract_multiplier(suggestion)
                ctx = build_driver_context(observed_t0_cost=observed_t0_cost, assumptions=DEFAULT_ASSUMPTIONS)
                suggested_driver, params_v3, warnings, _derived, val_result = resolve_driver_and_params(
                    suggestion=suggestion,
                    ctx=ctx,
                    override_driver=None,
                    horizon_months=horizon_months,
                    user_text=case.question,
                )
                params_out = _key_params(params_v3)
                summary, _details = summarize_warnings(
                    warnings=warnings + [w.message for w in getattr(val_result, "warnings", [])],
                    clamps=[c.message for c in getattr(val_result, "clamps", [])],
                    normalizations=[],
                    max_items=5,
                )
                warning_summary_count = len(summary)
                hard_fail = len(getattr(val_result, "errors", [])) > 0
                if hard_fail:
                    error = "; ".join([e.message for e in getattr(val_result, "errors", [])])
            except Exception as exc:  # noqa: BLE001 - keep run loop resilient
                hard_fail = True
                error = str(exc)
            latency_ms = int((time.perf_counter() - started) * 1000)
            rows.append(
                {
                    "id": case.case_id,
                    "run_index": run_idx,
                    "question": case.question,
                    "expected_driver": case.expected_driver,
                    "suggested_driver": suggested_driver,
                    "key_params": params_out,
                    "ten_year_multiplier_estimate": ten_year_multiplier,
                    "warning_summary_count": warning_summary_count,
                    "hard_fail": hard_fail,
                    "error": error,
                    "latency_ms": latency_ms,
                }
            )
    return rows


def write_jsonl(rows: Sequence[Dict[str, Any]], path: str | Path) -> Path:
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Run N evals per prompt and write JSONL stability results.")
    parser.add_argument("--csv", default="eval_questions_answers.csv", help="Path to eval question CSV.")
    parser.add_argument("--n", type=int, default=3, help="Runs per question.")
    parser.add_argument("--out", default="evals/results.jsonl", help="Output JSONL path.")
    parser.add_argument("--limit", type=int, default=0, help="Optional limit on question count.")
    parser.add_argument("--id", default="", help="Optional id filter, e.g. Q01 or Q01,Q07.")
    parser.add_argument("--skip-preflight", action="store_true", help="Skip LLM preflight checks.")
    args = parser.parse_args()

    if not args.skip_preflight:
        ok, msg = _preflight_llm()
        print(f"Preflight: {msg}")
        if not ok:
            raise SystemExit(2)

    cases = load_eval_cases(args.csv)
    if args.id.strip():
        ids = [p.strip() for p in args.id.split(",") if p.strip()]
        cases = select_eval_cases(cases, ids)
    if args.limit and args.limit > 0:
        cases = cases[: args.limit]

    rows = run_evals(cases, n=max(1, args.n))
    out_path = write_jsonl(rows, args.out)

    total = len(rows)
    hard_fails = sum(1 for r in rows if r.get("hard_fail"))
    print(f"Wrote: {out_path}")
    print(f"Rows: {total}")
    print(f"Hard failures: {hard_fails}")


if __name__ == "__main__":
    main()
