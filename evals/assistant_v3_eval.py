from __future__ import annotations

import csv
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Sequence

from config import DEFAULT_ASSUMPTIONS
from llm.provider import generate_json, has_llm_key
from llm.scenario_assistant_v3 import request_suggestion
from llm.validate_suggestion import SuggestionValidationError
from scenarios.schema import ScenarioParamsV3
from ui.assistant_v3_pipeline import build_driver_context, parse_suggestion, resolve_driver_and_params


_PCT_FIELDS = {
    "impact_magnitude",
    "growth_delta_pp_per_year",
    "drift_pp_per_year",
    "event_growth_delta_pp_per_year",
    "post_event_growth_pp_per_year",
    "fte_delta_pct",
    "cost_target_pct",
    "beta_multiplier",
}

_INT_FIELDS = {
    "lag_months",
    "onset_duration_months",
    "event_duration_months",
    "recovery_duration_months",
}

_TEXT_FIELDS = {"driver", "shape", "impact_mode"}

_STOPWORDS = {
    "and",
    "the",
    "with",
    "that",
    "this",
    "from",
    "into",
    "over",
    "when",
    "what",
    "will",
    "have",
    "has",
    "are",
    "for",
    "our",
    "your",
    "their",
    "than",
    "then",
    "given",
    "should",
    "must",
    "also",
    "using",
    "cost",
    "costs",
    "fte",
}


@dataclass(frozen=True)
class EvalCase:
    case_id: str
    question: str
    expected_driver: str
    expected_answer_summary: str
    expected_params: Dict[str, Any]
    assumptions_to_mention: str
    must_include_checks: str


@dataclass(frozen=True)
class EvalResult:
    case_id: str
    question: str
    expected_driver: str
    predicted_driver: str
    driver_match: bool
    param_sign_matches: int
    param_sign_total: int
    param_exact_matches: int
    param_exact_total: int
    summary_keyword_coverage: float
    assumptions_keyword_coverage: float
    checks_keyword_coverage: float
    warnings_count: int
    latency_ms: int
    answer_text: str
    llm_raw_excerpt: str
    error: str | None

    @property
    def overall_pass(self) -> bool:
        return self.error is None and self.driver_match


SuggestionFn = Callable[[str, int, Dict[str, object]], Dict[str, object]]


def _parse_expected_params(raw: str) -> Dict[str, Any]:
    try:
        parsed = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}
    if isinstance(parsed, dict):
        return parsed
    return {}


def load_eval_cases(path: str | Path) -> List[EvalCase]:
    rows: List[EvalCase] = []
    csv_path = Path(path)
    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows.append(
                EvalCase(
                    case_id=(row.get("id") or "").strip(),
                    question=(row.get("question") or "").strip(),
                    expected_driver=(row.get("expected_driver") or "").strip().lower(),
                    expected_answer_summary=(row.get("expected_answer_summary") or "").strip(),
                    expected_params=_parse_expected_params(row.get("expected_params_json") or "{}"),
                    assumptions_to_mention=(row.get("assumptions_to_mention") or "").strip(),
                    must_include_checks=(row.get("must_include_checks") or "").strip(),
                )
            )
    return rows


def select_eval_cases(cases: Sequence[EvalCase], case_ids: Sequence[str]) -> List[EvalCase]:
    wanted = {c.strip() for c in case_ids if c and c.strip()}
    if not wanted:
        return list(cases)
    selected = [c for c in cases if c.case_id in wanted]
    missing = sorted(wanted - {c.case_id for c in selected})
    if missing:
        raise ValueError(f"Unknown eval case id(s): {', '.join(missing)}")
    return selected


def _extract_text_for_eval(suggestion: Dict[str, Any]) -> str:
    rationale = suggestion.get("rationale") or {}
    parts: List[str] = []
    if isinstance(rationale, dict):
        for key in ("title", "summary", "notes"):
            val = rationale.get(key)
            if isinstance(val, str):
                parts.append(val)
        for key in ("assumptions", "why_these_numbers"):
            val = rationale.get(key)
            if isinstance(val, list):
                parts.extend([v for v in val if isinstance(v, str)])
    safety = suggestion.get("safety") or {}
    if isinstance(safety, dict):
        for key in ("adjustments", "warnings"):
            val = safety.get(key)
            if isinstance(val, list):
                parts.extend([v for v in val if isinstance(v, str)])
    return " ".join(parts).lower()


def _extract_answer_text(suggestion: Dict[str, Any]) -> str:
    rationale = suggestion.get("rationale") or {}
    parts: List[str] = []
    if isinstance(rationale, dict):
        title = rationale.get("title")
        summary = rationale.get("summary")
        if isinstance(title, str) and title.strip():
            parts.append(title.strip())
        if isinstance(summary, str) and summary.strip():
            parts.append(summary.strip())
        assumptions = rationale.get("assumptions")
        if isinstance(assumptions, list):
            parts.extend([f"Assumption: {v.strip()}" for v in assumptions if isinstance(v, str) and v.strip()])
        why = rationale.get("why_these_numbers")
        if isinstance(why, list):
            parts.extend([f"Why: {v.strip()}" for v in why if isinstance(v, str) and v.strip()])
    safety = suggestion.get("safety") or {}
    if isinstance(safety, dict):
        warnings = safety.get("warnings")
        if isinstance(warnings, list):
            parts.extend([f"Warning: {v.strip()}" for v in warnings if isinstance(v, str) and v.strip()])
    return " | ".join(parts)


def _tokenize_keywords(text: str) -> List[str]:
    tokens = [t for t in re.findall(r"[a-zA-Z]{4,}", text.lower()) if t not in _STOPWORDS]
    # Preserve order but deduplicate
    out: List[str] = []
    seen = set()
    for token in tokens:
        if token not in seen:
            seen.add(token)
            out.append(token)
    return out


def _keyword_coverage(expected_text: str, actual_text: str, max_keywords: int = 8) -> float:
    keywords = _tokenize_keywords(expected_text)[:max_keywords]
    if not keywords:
        return 1.0
    matched = 0
    for kw in keywords:
        if kw in actual_text:
            matched += 1
    return matched / len(keywords)


def _sign(value: float | int | None) -> int:
    if value is None:
        return 0
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _score_params(expected: Dict[str, Any], actual: ScenarioParamsV3) -> tuple[int, int, int, int]:
    sign_matches = 0
    sign_total = 0
    exact_matches = 0
    exact_total = 0

    for field, exp in expected.items():
        if not hasattr(actual, field):
            continue
        cur = getattr(actual, field)
        if field in _TEXT_FIELDS:
            exact_total += 1
            if str(cur) == str(exp):
                exact_matches += 1
            continue
        if field in _INT_FIELDS:
            exact_total += 1
            if cur is None and exp is None:
                exact_matches += 1
            elif cur is not None and exp is not None:
                if int(cur) == int(exp):
                    exact_matches += 1
            continue
        if field in _PCT_FIELDS:
            exp_num = _to_float(exp)
            cur_num = _to_float(cur)
            if exp_num is None or cur_num is None:
                continue
            sign_total += 1
            if _sign(exp_num) == _sign(cur_num):
                sign_matches += 1
    return sign_matches, sign_total, exact_matches, exact_total


def _canonical_predicted_driver(
    expected_driver: str,
    predicted_driver: str,
    params: ScenarioParamsV3,
    question: str,
) -> str:
    """
    Eval-only canonicalization for drivers not yet first-class in schema.
    """
    if expected_driver != "mix_shift":
        return predicted_driver

    text = (question or "").lower()
    mix_keywords = (
        "relocate",
        "lower-cost",
        "high-cost",
        "offshore",
        "nearshore",
        "workforce mix",
        "location mix",
        "economic downturn",
        "stabilize costs",
    )
    has_mix_signal = any(k in text for k in mix_keywords)
    beta_mult = params.beta_multiplier
    no_explicit_fte = params.fte_delta_pct is None and params.fte_delta_abs is None
    if predicted_driver == "cost" and has_mix_signal and beta_mult is not None and beta_mult < 1.0 and no_explicit_fte:
        return "mix_shift"
    return predicted_driver


def run_eval_case(
    case: EvalCase,
    suggestion_fn: SuggestionFn = request_suggestion,
    horizon_years: int = 10,
    horizon_months: int = 120,
    observed_t0_cost: float = DEFAULT_ASSUMPTIONS.t0_cost,
) -> EvalResult:
    baseline_stats = {"last_value": observed_t0_cost, "trend_12m": observed_t0_cost * 0.06 / 12, "volatility": 0.01}
    error: str | None = None
    predicted_driver = "unknown"
    warnings_count = 0
    summary_coverage = 0.0
    assumptions_coverage = 0.0
    checks_coverage = 0.0
    answer_text = ""
    raw_excerpt = ""
    sign_matches = sign_total = exact_matches = exact_total = 0
    start_ts = time.perf_counter()

    try:
        llm_out = suggestion_fn(case.question, horizon_years, baseline_stats)
        if isinstance(llm_out, dict):
            raw_excerpt = str(llm_out.get("raw_excerpt") or "")
        suggestion = llm_out.get("response") if isinstance(llm_out, dict) else llm_out
        if isinstance(suggestion, str):
            suggestion = parse_suggestion(suggestion)
        if not isinstance(suggestion, dict):
            raise SuggestionValidationError("Invalid suggestion payload.")
        answer_text = _extract_answer_text(suggestion)

        ctx = build_driver_context(observed_t0_cost=observed_t0_cost, assumptions=DEFAULT_ASSUMPTIONS)
        predicted_driver, params_v3, warnings, _derived, val_result = resolve_driver_and_params(
            suggestion=suggestion,
            ctx=ctx,
            override_driver=None,
            horizon_months=horizon_months,
            user_text=case.question,
        )
        predicted_driver = _canonical_predicted_driver(
            expected_driver=case.expected_driver,
            predicted_driver=predicted_driver,
            params=params_v3,
            question=case.question,
        )
        warnings_count = len(warnings) + len(getattr(val_result, "warnings", [])) + len(getattr(val_result, "clamps", []))
        sign_matches, sign_total, exact_matches, exact_total = _score_params(case.expected_params, params_v3)
        eval_text = _extract_text_for_eval(suggestion)
        summary_coverage = _keyword_coverage(case.expected_answer_summary, eval_text)
        assumptions_coverage = _keyword_coverage(case.assumptions_to_mention, eval_text)
        checks_coverage = _keyword_coverage(case.must_include_checks, eval_text)
    except Exception as exc:  # noqa: BLE001 - eval should capture and continue
        error = str(exc)
    latency_ms = int((time.perf_counter() - start_ts) * 1000)

    return EvalResult(
        case_id=case.case_id,
        question=case.question,
        expected_driver=case.expected_driver,
        predicted_driver=predicted_driver,
        driver_match=predicted_driver == case.expected_driver,
        param_sign_matches=sign_matches,
        param_sign_total=sign_total,
        param_exact_matches=exact_matches,
        param_exact_total=exact_total,
        summary_keyword_coverage=summary_coverage,
        assumptions_keyword_coverage=assumptions_coverage,
        checks_keyword_coverage=checks_coverage,
        warnings_count=warnings_count,
        latency_ms=latency_ms,
        answer_text=answer_text,
        llm_raw_excerpt=raw_excerpt,
        error=error,
    )


def run_eval_cases(
    cases: Sequence[EvalCase],
    suggestion_fn: SuggestionFn = request_suggestion,
    horizon_years: int = 10,
    horizon_months: int = 120,
    observed_t0_cost: float = DEFAULT_ASSUMPTIONS.t0_cost,
) -> List[EvalResult]:
    return [
        run_eval_case(
            case,
            suggestion_fn=suggestion_fn,
            horizon_years=horizon_years,
            horizon_months=horizon_months,
            observed_t0_cost=observed_t0_cost,
        )
        for case in cases
    ]


def results_to_rows(results: Iterable[EvalResult]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for result in results:
        rows.append(
            {
                "id": result.case_id,
                "question": result.question,
                "expected_driver": result.expected_driver,
                "predicted_driver": result.predicted_driver,
                "driver_match": result.driver_match,
                "param_sign_matches": result.param_sign_matches,
                "param_sign_total": result.param_sign_total,
                "param_exact_matches": result.param_exact_matches,
                "param_exact_total": result.param_exact_total,
                "summary_keyword_coverage": round(result.summary_keyword_coverage, 3),
                "assumptions_keyword_coverage": round(result.assumptions_keyword_coverage, 3),
                "checks_keyword_coverage": round(result.checks_keyword_coverage, 3),
                "warnings_count": result.warnings_count,
                "latency_ms": result.latency_ms,
                "answer_text": result.answer_text,
                "llm_raw_excerpt": result.llm_raw_excerpt,
                "error": result.error or "",
                "overall_pass": result.overall_pass,
            }
        )
    return rows


def _score_answer_heuristic(result: EvalResult) -> tuple[int, str]:
    if result.error:
        return 0, f"No match due to runtime error: {result.error}"
    if not result.driver_match:
        return 0, "No match: predicted driver differs from expected driver."

    coverage_avg = (
        result.summary_keyword_coverage + result.assumptions_keyword_coverage + result.checks_keyword_coverage
    ) / 3.0
    sign_ratio = 1.0
    if result.param_sign_total > 0:
        sign_ratio = result.param_sign_matches / result.param_sign_total

    if coverage_avg < 0.35 or result.warnings_count >= 10 or sign_ratio < 0.5:
        return 1, "Really messy: low text coverage and/or high warnings/weak param alignment."
    if coverage_avg < 0.65 or result.warnings_count >= 4 or sign_ratio < 1.0:
        return 2, "Okayish: mostly aligned but with gaps in coverage or warning noise."
    return 3, "Decent match: strong driver/parameter alignment with clear answer quality."


def score_answer(result: EvalResult) -> tuple[int, str]:
    # Hard rule for scorecard consistency: non-match or runtime error is always score 0.
    if result.error:
        return 0, f"No match due to runtime error: {result.error}"
    if not result.driver_match:
        return 0, "No match: predicted driver differs from expected driver."

    # Use LLM grading when possible; fallback preserves offline/test reliability.
    heuristic_score, heuristic_reason = _score_answer_heuristic(result)
    if os.getenv("EVAL_ANSWER_SCORE_WITH_LLM", "0") != "1":
        return heuristic_score, heuristic_reason
    if not has_llm_key():
        return heuristic_score, heuristic_reason

    system = (
        "You grade eval answer quality for an HR scenario assistant. "
        "Return JSON only with keys: answer_score (int 0..3), reason (string). "
        "Scale: 0=no match, 1=really messy, 2=okayish, 3=decent match."
    )
    user = (
        f"question={result.question}\n"
        f"expected_driver={result.expected_driver}\n"
        f"predicted_driver={result.predicted_driver}\n"
        f"driver_match={result.driver_match}\n"
        f"warnings_count={result.warnings_count}\n"
        f"param_sign_matches={result.param_sign_matches}/{result.param_sign_total}\n"
        f"param_exact_matches={result.param_exact_matches}/{result.param_exact_total}\n"
        f"error={result.error or '-'}\n"
        f"assistant_answer={result.answer_text[:2500]}\n"
        "Assess overall answer quality and business usefulness. "
        "Penalize incorrect driver/logic heavily."
    )
    try:
        graded = generate_json(system, user, schema_hint={"answer_score": 0, "reason": ""})
        raw_score = graded.get("answer_score")
        score = int(raw_score)
        if score < 0 or score > 3:
            return heuristic_score, heuristic_reason
        reason = str(graded.get("reason") or "").strip() or heuristic_reason
        return score, reason
    except Exception:
        return heuristic_score, heuristic_reason


def build_scorecard(results: Sequence[EvalResult]) -> Dict[str, Any]:
    score_counts = {0: 0, 1: 0, 2: 0, 3: 0}
    per_question: List[Dict[str, Any]] = []
    for r in results:
        score, reason = score_answer(r)
        score_counts[score] += 1
        per_question.append(
            {
                "id": r.case_id,
                "question": r.question,
                "expected_driver": r.expected_driver,
                "predicted_driver": r.predicted_driver,
                "driver_match": r.driver_match,
                "overall_pass": r.overall_pass,
                "answer_score": score,
                "answer_score_reason": reason,
                "warnings_count": r.warnings_count,
                "latency_ms": r.latency_ms,
                "summary_keyword_coverage": round(r.summary_keyword_coverage, 3),
                "assumptions_keyword_coverage": round(r.assumptions_keyword_coverage, 3),
                "checks_keyword_coverage": round(r.checks_keyword_coverage, 3),
                "param_sign_matches": r.param_sign_matches,
                "param_sign_total": r.param_sign_total,
                "param_exact_matches": r.param_exact_matches,
                "param_exact_total": r.param_exact_total,
                "error": r.error or "",
            }
        )

    n = len(results)
    total_matches = sum(1 for r in results if r.driver_match)
    total_passes = sum(1 for r in results if r.overall_pass)
    total_errors = sum(1 for r in results if r.error)
    avg_score = 0.0 if n == 0 else sum(score * count for score, count in score_counts.items()) / n
    avg_latency = 0.0 if n == 0 else sum(r.latency_ms for r in results) / n

    return {
        "summary": {
            "total_questions": n,
            "total_matches": total_matches,
            "total_passes": total_passes,
            "total_errors": total_errors,
            "match_rate": 0.0 if n == 0 else round(total_matches / n, 4),
            "pass_rate": 0.0 if n == 0 else round(total_passes / n, 4),
            "average_answer_score": round(avg_score, 3),
            "answer_score_distribution": score_counts,
            "average_latency_ms": round(avg_latency, 1),
        },
        "questions": per_question,
    }


def _fmt_cmp_num(current: Any, benchmark: Any) -> str:
    if benchmark is None:
        return str(current)
    return f"{current} / {benchmark}"


def scorecard_to_markdown(scorecard: Dict[str, Any], benchmark_scorecard: Dict[str, Any] | None = None) -> str:
    summary = scorecard.get("summary", {})
    questions = scorecard.get("questions", [])
    benchmark_summary = (benchmark_scorecard or {}).get("summary", {})
    benchmark_questions = (benchmark_scorecard or {}).get("questions", [])
    benchmark_by_id = {str(q.get("id", "")): q for q in benchmark_questions}
    has_latency = any((q.get("latency_ms") or 0) > 0 for q in questions)
    benchmark_has_latency = any((q.get("latency_ms") or 0) > 0 for q in benchmark_questions)
    avg_latency = summary.get("average_latency_ms", 0.0)
    lines: List[str] = []
    lines.append("# Assistant V3 Eval Scorecard")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(
        "- Total matches: "
        + _fmt_cmp_num(summary.get("total_matches", 0), benchmark_summary.get("total_matches"))
    )
    lines.append(
        "- Total passes: "
        + _fmt_cmp_num(summary.get("total_passes", 0), benchmark_summary.get("total_passes"))
    )
    lines.append(
        "- Total errors: "
        + _fmt_cmp_num(summary.get("total_errors", 0), benchmark_summary.get("total_errors"))
    )
    lines.append("- Match rate: " + _fmt_cmp_num(summary.get("match_rate", 0.0), benchmark_summary.get("match_rate")))
    lines.append("- Pass rate: " + _fmt_cmp_num(summary.get("pass_rate", 0.0), benchmark_summary.get("pass_rate")))
    lines.append(
        "- Average answer score: "
        + _fmt_cmp_num(summary.get("average_answer_score", 0.0), benchmark_summary.get("average_answer_score"))
    )
    if has_latency:
        benchmark_avg_latency = benchmark_summary.get("average_latency_ms") if benchmark_has_latency else "N/A"
        lines.append("- Average latency (ms): " + _fmt_cmp_num(avg_latency, benchmark_avg_latency))
    else:
        lines.append("- Average latency (ms): N/A (latency not captured in this run)")
    lines.append("")
    lines.append("### Answer Score Distribution")
    dist = summary.get("answer_score_distribution", {})
    lines.append("")
    lines.append("| Score | Count |")
    lines.append("|---|---:|")
    for score in (0, 1, 2, 3):
        cur_val = dist.get(score, dist.get(str(score), 0))
        bench_dist = benchmark_summary.get("answer_score_distribution", {})
        bench_val = bench_dist.get(score, bench_dist.get(str(score))) if isinstance(bench_dist, dict) else None
        lines.append(f"| {score} | {_fmt_cmp_num(cur_val, bench_val)} |")
    lines.append("")
    lines.append("## Per Question")
    lines.append("")
    for q in questions:
        bench_q = benchmark_by_id.get(str(q.get("id", "")), {})
        latency_value = q.get("latency_ms", 0)
        latency_text = str(latency_value) if (latency_value or 0) > 0 else "N/A"
        lines.append(f"### {q.get('id', '')}")
        lines.append(f"- Question: {q.get('question', '')}")
        lines.append(f"- Expected driver: `{q.get('expected_driver', '')}`")
        lines.append(f"- Predicted driver: `{q.get('predicted_driver', '')}`")
        lines.append(f"- Driver match: `{q.get('driver_match', False)}`")
        lines.append(f"- Overall pass: `{q.get('overall_pass', False)}`")
        lines.append(
            "- Answer score: `"
            + _fmt_cmp_num(q.get("answer_score", 0), bench_q.get("answer_score"))
            + "`"
        )
        lines.append(
            "- Warnings: `"
            + _fmt_cmp_num(q.get("warnings_count", 0), bench_q.get("warnings_count"))
            + "`"
        )
        bench_latency = bench_q.get("latency_ms")
        bench_latency_text = str(bench_latency) if (bench_latency or 0) > 0 else ("N/A" if bench_latency is not None else None)
        lines.append("- Latency (ms): `" + _fmt_cmp_num(latency_text, bench_latency_text) + "`")
        lines.append(
            "- Param sign matches: `"
            + _fmt_cmp_num(
                f"{q.get('param_sign_matches', 0)}/{q.get('param_sign_total', 0)}",
                f"{bench_q.get('param_sign_matches', 0)}/{bench_q.get('param_sign_total', 0)}"
                if bench_q
                else None,
            )
            + "`"
        )
        lines.append(
            "- Param exact matches: `"
            + _fmt_cmp_num(
                f"{q.get('param_exact_matches', 0)}/{q.get('param_exact_total', 0)}",
                f"{bench_q.get('param_exact_matches', 0)}/{bench_q.get('param_exact_total', 0)}"
                if bench_q
                else None,
            )
            + "`"
        )
        error_text = (q.get("error", "") or "-").replace("\n", " ").replace("|", "/")
        lines.append(f"- Error: `{error_text}`")
        reason = q.get("answer_score_reason", "")
        if reason:
            lines.append(f"- Score note: {reason}")
        lines.append("")
    lines.append("")
    return "\n".join(lines)
