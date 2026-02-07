from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path

from evals.assistant_v3_eval import (
    build_scorecard,
    load_eval_cases,
    results_to_rows,
    run_eval_cases,
    scorecard_to_markdown,
    select_eval_cases,
)
from llm.provider import LLMError, has_llm_key, list_models, model_name, provider_name

DEFAULT_BENCHMARK_PATH = Path("evals/benchmark/assistant_v3_eval_benchmark.json")


def _write_rows(rows: list[dict], out_path: Path) -> None:
    if not rows:
        return
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _write_json(payload: dict, out_path: Path) -> None:
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_text(payload: str, out_path: Path) -> None:
    out_path.write_text(payload, encoding="utf-8")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _apply_eval_llm_limits(
    timeout_seconds: int | None,
    max_retries: int | None,
    max_tokens: int | None,
) -> tuple[int, int, int]:
    # Eval runs are batch-heavy; use conservative minimums so single cases are less likely to fail on latency.
    current_timeout = int(os.getenv("LLM_TIMEOUT_SECONDS", "600"))
    current_retries = int(os.getenv("LLM_MAX_RETRIES", "2"))
    current_tokens = int(os.getenv("LLM_MAX_TOKENS", "2048"))

    effective_timeout = timeout_seconds if timeout_seconds is not None else max(current_timeout, 900)
    effective_retries = max_retries if max_retries is not None else max(current_retries, 4)
    effective_tokens = max_tokens if max_tokens is not None else max(current_tokens, 4096)

    os.environ["LLM_TIMEOUT_SECONDS"] = str(effective_timeout)
    os.environ["LLM_MAX_RETRIES"] = str(effective_retries)
    os.environ["LLM_MAX_TOKENS"] = str(effective_tokens)
    return effective_timeout, effective_retries, effective_tokens


def _preflight_llm() -> tuple[bool, str]:
    if not has_llm_key():
        return False, "Missing LLM API key."
    provider = provider_name()
    model = model_name()
    try:
        models = list_models()
    except LLMError as exc:
        reason = str(exc)
        hints = {
            "llm_dns_error": "DNS resolution failed; check internet/DNS and ANTHROPIC_API_BASE.",
            "llm_timeout": "Network timeout; check connectivity, proxy, or increase LLM timeout.",
            "llm_connection_refused": "Connection refused; check firewall/proxy and API base URL.",
            "llm_ssl_error": "TLS/SSL error; check system certs/proxy SSL interception.",
            "llm_network_error": "Network error; check internet/proxy settings.",
            "llm_http_401_invalid_key": "Invalid API key.",
        }
        return False, f"{reason}: {hints.get(reason, 'LLM connection failed.')}"

    if model not in models:
        return False, f"Model '{model}' not available for provider '{provider}'."
    return True, f"LLM OK ({provider}, model={model})"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one-step V3 assistant evals from CSV questions.")
    parser.add_argument(
        "--csv",
        default="eval_questions_answers.csv",
        help="Path to evaluation CSV file (default: eval_questions_answers.csv)",
    )
    parser.add_argument("--limit", type=int, default=0, help="Optional limit on number of eval rows")
    parser.add_argument(
        "--id",
        default="",
        help="Run only a specific case id (or comma-separated ids), e.g. Q01 or Q01,Q07",
    )
    parser.add_argument("--out", default="", help="Optional output CSV path for per-case log")
    parser.add_argument("--log-out", default="", help="Optional explicit output CSV path for per-case log")
    parser.add_argument("--scorecard-out", default="", help="Optional explicit output JSON path for scorecard")
    parser.add_argument("--scorecard-md-out", default="", help="Optional explicit output Markdown path for scorecard")
    parser.add_argument(
        "--benchmark-in",
        default="",
        help="Optional benchmark scorecard JSON path for current/benchmark comparison in Markdown.",
    )
    parser.add_argument(
        "--benchmark-out",
        default="",
        help="Optional path to store current run scorecard as benchmark JSON.",
    )
    parser.add_argument(
        "--llm-timeout-seconds",
        type=int,
        default=None,
        help="Override LLM request timeout for this eval run.",
    )
    parser.add_argument(
        "--llm-max-retries",
        type=int,
        default=None,
        help="Override LLM retry count for this eval run.",
    )
    parser.add_argument(
        "--llm-max-tokens",
        type=int,
        default=None,
        help="Override LLM max output tokens for this eval run.",
    )
    parser.add_argument(
        "--skip-preflight",
        action="store_true",
        help="Skip LLM connectivity preflight (not recommended).",
    )
    args = parser.parse_args()

    timeout, retries, tokens = _apply_eval_llm_limits(
        args.llm_timeout_seconds,
        args.llm_max_retries,
        args.llm_max_tokens,
    )
    os.environ["EVAL_ANSWER_SCORE_WITH_LLM"] = "1"
    print(f"LLM limits: timeout={timeout}s retries={retries} max_tokens={tokens}")

    if not args.skip_preflight:
        ok, message = _preflight_llm()
        print(f"Preflight: {message}")
        if not ok:
            raise SystemExit(2)

    cases = load_eval_cases(args.csv)
    if args.id.strip():
        case_ids = [p.strip() for p in args.id.split(",") if p.strip()]
        cases = select_eval_cases(cases, case_ids)
    if args.limit and args.limit > 0:
        cases = cases[: args.limit]

    results = run_eval_cases(cases)
    rows = results_to_rows(results)
    scorecard = build_scorecard(results)

    total = len(results)
    errors = sum(1 for r in results if r.error)
    driver_match = sum(1 for r in results if r.driver_match)
    passed = sum(1 for r in results if r.overall_pass)

    print(f"Cases: {total}")
    print(f"Driver match: {driver_match}/{total}")
    print(f"Overall pass: {passed}/{total}")
    print(f"Errors: {errors}")
    print(f"Average answer score: {scorecard['summary']['average_answer_score']}")

    log_out = args.log_out or args.out
    scorecard_out = args.scorecard_out
    scorecard_md_out = args.scorecard_md_out
    benchmark_in = args.benchmark_in
    benchmark_out = args.benchmark_out
    if not scorecard_out and (args.out or args.log_out):
        target = Path(log_out)
        scorecard_out = str(target.with_name(f"{target.stem}_scorecard.json"))
    if not scorecard_md_out and (args.out or args.log_out):
        target = Path(log_out)
        scorecard_md_out = str(target.with_name(f"{target.stem}_scorecard.md"))
    if not benchmark_out:
        benchmark_out = str(DEFAULT_BENCHMARK_PATH)

    benchmark_scorecard = None
    benchmark_source = benchmark_in or str(DEFAULT_BENCHMARK_PATH)
    if benchmark_source:
        benchmark_path = Path(benchmark_source)
        if benchmark_path.exists():
            benchmark_scorecard = _read_json(benchmark_path)
            print(f"Loaded benchmark: {benchmark_path}")
        elif benchmark_in:
            print(f"Benchmark not found (skipping compare): {benchmark_path}")

    if log_out:
        log_path = Path(log_out)
        _write_rows(rows, log_path)
        print(f"Wrote eval log: {log_path}")
    if scorecard_out:
        score_path = Path(scorecard_out)
        _write_json(scorecard, score_path)
        print(f"Wrote scorecard: {score_path}")
    if benchmark_out:
        benchmark_path = Path(benchmark_out)
        benchmark_path.parent.mkdir(parents=True, exist_ok=True)
        _write_json(scorecard, benchmark_path)
        print(f"Wrote benchmark: {benchmark_path}")
    if scorecard_md_out:
        md_path = Path(scorecard_md_out)
        _write_text(scorecard_to_markdown(scorecard, benchmark_scorecard=benchmark_scorecard), md_path)
        print(f"Wrote scorecard (md): {md_path}")

    # Print compact per-case output for quick triage
    for row in rows:
        print(
            f"[{row['id']}] driver={row['predicted_driver']} match={row['driver_match']} "
            f"warn={row['warnings_count']} err={row['error'] or '-'}"
        )

    # Bug-fixing loop helper: return non-zero if any case is not a pass.
    if passed < total:
        raise SystemExit(3)


if __name__ == "__main__":
    main()
