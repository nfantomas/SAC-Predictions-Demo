from __future__ import annotations

import argparse
import json
import os
import statistics
import time
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Dict, List, Sequence

from evals.generate_answer import generate_answer
from evals.grader import grade_answer
from evals.load_evalset import EvalRow, load_evalset
from llm.provider import LLMError, has_llm_key, list_models, model_name, provider_name


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


def _safe_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def _safe_write_jsonl(path: Path, rows: Sequence[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")


def _params_subset(params: Dict[str, Any]) -> Dict[str, Any]:
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
    return {k: params.get(k) for k in keys}


def _collect_tags(graded_rows: Sequence[Dict[str, Any]]) -> Counter:
    tags = Counter()
    for row in graded_rows:
        for tag in row.get("grader", {}).get("tags", []):
            if isinstance(tag, str):
                tags[tag] += 1
    return tags


def _build_summary(graded_rows: Sequence[Dict[str, Any]], failures: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    scores = [int(row["grader"]["score"]) for row in graded_rows if isinstance(row.get("grader"), dict)]
    score_hist = {str(i): 0 for i in range(4)}
    for score in scores:
        score_hist[str(score)] += 1
    mean_score = float(statistics.fmean(scores)) if scores else 0.0

    latencies = [int(row.get("latency_ms", 0)) for row in graded_rows]
    mean_latency = float(statistics.fmean(latencies)) if latencies else 0.0
    hard_fail_pct = (len(failures) / len(graded_rows) * 100.0) if graded_rows else 0.0

    top_tags = _collect_tags(graded_rows).most_common(10)
    lowest = sorted(graded_rows, key=lambda r: (int(r.get("grader", {}).get("score", 99)), r.get("id", "")))[:5]
    lowest_ids = [item.get("id", "") for item in lowest]

    return {
        "runs": len(graded_rows),
        "questions": len({row.get("id") for row in graded_rows}),
        "mean_score": round(mean_score, 4),
        "score_histogram": score_hist,
        "hard_failures": len(failures),
        "hard_failure_pct": round(hard_fail_pct, 2),
        "mean_latency_ms": round(mean_latency, 2),
        "top_tags": [{"tag": tag, "count": count} for tag, count in top_tags],
        "lowest_scoring_ids": lowest_ids,
    }


def _stub_generate_answer(question: str) -> Dict[str, Any]:
    q = question.lower()
    driver = "cost"
    if "fte" in q or "headcount" in q or "hiring" in q or "attrition" in q:
        driver = "fte"
    if "cost target" in q or "keep total cost flat" in q or "reduce cost" in q:
        driver = "cost_target"
    return {
        "error_type": "",
        "error_message": "",
        "model_output_json": {"safety": {"adjustments": []}},
        "applied_params": {"driver": driver, "lag_months": 6, "onset_duration_months": 3},
        "summary_text": "Smoke mode deterministic answer.",
        "key_metrics": {
            "driver": driver,
            "warnings_count": 0,
            "deterministic_ten_year_multiplier": 1.0,
            "clarification_required": False,
            "provider": "stub",
            "model": "stub",
            "fallback_used": False,
        },
    }


def _stub_grade_answer(**_kwargs: Any) -> Dict[str, Any]:
    return {
        "score": 2,
        "reasoning": "Smoke mode stub grader result.",
        "tags": ["clarity"],
        "suggested_fix": ["Run full eval mode for real grading."],
    }


def _run_one(
    row: EvalRow,
    run_idx: int,
    answer_fn: Callable[[str], Dict[str, Any]],
    grader_fn: Callable[..., Dict[str, Any]],
) -> Dict[str, Any]:
    started = time.perf_counter()
    answer = answer_fn(row.question)

    error_type = str(answer.get("error_type") or "")
    error_message = str(answer.get("error_message") or "")
    hard_fail = bool(error_type)

    model_json = answer.get("model_output_json") if isinstance(answer.get("model_output_json"), dict) else {}
    applied_params = answer.get("applied_params") if isinstance(answer.get("applied_params"), dict) else {}
    key_metrics = answer.get("key_metrics") if isinstance(answer.get("key_metrics"), dict) else {}

    summary_text = str(answer.get("summary_text") or "")
    model_payload = {
        "summary_text": summary_text,
        "applied_params": _params_subset(applied_params),
        "key_metrics": key_metrics,
        "model_output_json": model_json,
    }
    grade = grader_fn(
        question=row.question,
        expected_answer=row.expected_answer,
        model_answer=model_payload,
    )

    safety = model_json.get("safety") if isinstance(model_json, dict) else {}
    adjustments = safety.get("adjustments") if isinstance(safety, dict) and isinstance(safety.get("adjustments"), list) else []

    latency_ms = int((time.perf_counter() - started) * 1000)
    return {
        "id": row.id,
        "run_index": run_idx,
        "question": row.question,
        "expected_answer": row.expected_answer,
        "summary_text": summary_text,
        "model_driver": key_metrics.get("driver", "unknown"),
        "key_params": _params_subset(applied_params),
        "warnings_count": int(key_metrics.get("warnings_count", 0) or 0),
        "clamp_summary": adjustments,
        "deterministic_ten_year_multiplier": key_metrics.get("deterministic_ten_year_multiplier"),
        "grader": grade,
        "hard_fail": hard_fail,
        "error_type": error_type,
        "error": error_message,
        "latency_ms": latency_ms,
    }


def run_consulting_evals(
    rows: Sequence[EvalRow],
    n: int,
    *,
    answer_fn: Callable[[str], Dict[str, Any]] | None = None,
    grader_fn: Callable[..., Dict[str, Any]] | None = None,
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    all_rows: List[Dict[str, Any]] = []
    failures: List[Dict[str, Any]] = []
    use_answer = answer_fn or generate_answer
    use_grader = grader_fn or grade_answer
    for row in rows:
        for run_idx in range(1, max(1, n) + 1):
            out = _run_one(row, run_idx, answer_fn=use_answer, grader_fn=use_grader)
            all_rows.append(out)
            if out.get("hard_fail"):
                failures.append(out)
    summary = _build_summary(all_rows, failures)
    return all_rows, failures, summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run consulting assistant evals with LLM grading.")
    parser.add_argument("--csv", default="evals/data/consulting_eval_questions_answers.csv", help="Eval CSV path.")
    parser.add_argument("--n", type=int, default=1, help="Runs per question.")
    parser.add_argument("--out", default="evals/out", help="Output directory.")
    parser.add_argument("--limit", type=int, default=0, help="Optional row limit.")
    parser.add_argument("--id", default="", help="Optional id filter: Q01 or Q01,Q05")
    parser.add_argument("--skip-preflight", action="store_true", help="Skip LLM provider/model preflight.")
    args = parser.parse_args()

    smoke_mode = os.getenv("EVALS_SMOKE_MODE", "").strip() == "1"
    if not args.skip_preflight and not smoke_mode:
        ok, msg = _preflight_llm()
        print(f"Preflight: {msg}")
        if not ok:
            raise SystemExit(2)

    rows = load_evalset(args.csv)
    if args.id.strip():
        wanted = {item.strip() for item in args.id.split(",") if item.strip()}
        rows = [row for row in rows if row.id in wanted]
    if args.limit and args.limit > 0:
        rows = rows[: args.limit]
    if smoke_mode:
        rows = rows[:5]

    results, failures, summary = run_consulting_evals(
        rows,
        n=args.n,
        answer_fn=_stub_generate_answer if smoke_mode else None,
        grader_fn=_stub_grade_answer if smoke_mode else None,
    )
    out_dir = Path(args.out)
    _safe_write_jsonl(out_dir / "results.jsonl", results)
    _safe_write_json(out_dir / "summary.json", summary)
    _safe_write_jsonl(out_dir / "failures.jsonl", failures)

    print(f"Results: {out_dir / 'results.jsonl'} ({len(results)} rows)")
    print(f"Summary: {out_dir / 'summary.json'}")
    print(f"Failures: {out_dir / 'failures.jsonl'} ({len(failures)} rows)")
    print(f"Mean score: {summary['mean_score']}")
    print(f"Hard failures: {summary['hard_failures']} ({summary['hard_failure_pct']}%)")
    print(f"Top tags: {summary['top_tags'][:5]}")
    print(f"Lowest scoring ids: {summary['lowest_scoring_ids']}")
    if smoke_mode:
        print("Smoke mode enabled via EVALS_SMOKE_MODE=1 (stub answer + stub grader).")


if __name__ == "__main__":
    main()
