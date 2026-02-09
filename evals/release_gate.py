from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List


SHOCK_KEYWORDS = (
    "war",
    "attack",
    "invasion",
    "sanction",
    "embargo",
    "mobilization",
    "terror",
    "capital controls",
    "cyberattack",
    "energy cutoff",
    "extreme",
    "worst case",
)


def _is_shock_prompt(question: str) -> bool:
    text = (question or "").lower()
    return any(token in text for token in SHOCK_KEYWORDS)


def _load_jsonl(path: str | Path) -> List[Dict]:
    rows: List[Dict] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            raw = line.strip()
            if not raw:
                continue
            rows.append(json.loads(raw))
    return rows


def _driver_stability(rows: List[Dict]) -> Dict[str, float]:
    per_prompt: Dict[str, List[str]] = defaultdict(list)
    for row in rows:
        per_prompt[row.get("id", "")].append(str(row.get("applied_driver", "unknown")))
    out: Dict[str, float] = {}
    for case_id, drivers in per_prompt.items():
        if not drivers:
            out[case_id] = 0.0
            continue
        mode_count = Counter(drivers).most_common(1)[0][1]
        out[case_id] = mode_count / len(drivers)
    return out


def _multiplier_ranges(rows: List[Dict]) -> Dict[str, float]:
    per_prompt: Dict[str, List[float]] = defaultdict(list)
    for row in rows:
        raw = row.get("deterministic_ten_year_multiplier")
        try:
            val = float(raw)
        except (TypeError, ValueError):
            continue
        per_prompt[row.get("id", "")].append(val)
    out: Dict[str, float] = {}
    for case_id, values in per_prompt.items():
        if not values:
            out[case_id] = 0.0
            continue
        out[case_id] = max(values) - min(values)
    return out


def evaluate_release_gate(
    rows: List[Dict],
    min_apply_rate: float = 0.98,
    min_driver_stability: float = 0.8,
    max_multiplier_range: float = 0.3,
    non_shock_min: float = 0.2,
    non_shock_max: float = 3.0,
    shock_max: float = 8.0,
) -> Dict[str, object]:
    total = len(rows)
    if total == 0:
        return {
            "ok": False,
            "checks": {"non_empty": False},
            "summary": {"rows": 0},
            "failures": ["No rows found in results file."],
        }

    hard_fails = sum(1 for r in rows if bool(r.get("hard_fail")))
    apply_rate = (total - hard_fails) / total

    warning_over_5 = sum(1 for r in rows if int(r.get("warning_summary_count", 0) or 0) > 5)
    warnings_ok = warning_over_5 == 0

    multiplier_failures = 0
    for row in rows:
        raw = row.get("deterministic_ten_year_multiplier")
        try:
            val = float(raw)
        except (TypeError, ValueError):
            continue
        q = str(row.get("question", ""))
        if _is_shock_prompt(q):
            if not (non_shock_min <= val <= shock_max):
                multiplier_failures += 1
        else:
            if not (non_shock_min <= val <= non_shock_max):
                multiplier_failures += 1

    stability = _driver_stability(rows)
    stability_ok = all(v >= min_driver_stability for v in stability.values())

    ranges = _multiplier_ranges(rows)
    ranges_ok = all(v <= max_multiplier_range for v in ranges.values())

    checks = {
        "apply_rate_ok": apply_rate >= min_apply_rate,
        "warnings_ok": warnings_ok,
        "multiplier_bounds_ok": multiplier_failures == 0,
        "driver_stability_ok": stability_ok,
        "multiplier_range_ok": ranges_ok,
    }

    failures: List[str] = []
    if not checks["apply_rate_ok"]:
        failures.append(f"Apply rate {apply_rate:.2%} below {min_apply_rate:.2%}.")
    if not checks["warnings_ok"]:
        failures.append(f"{warning_over_5} row(s) exceed warning summary cap of 5.")
    if not checks["multiplier_bounds_ok"]:
        failures.append(f"{multiplier_failures} row(s) violate conditional multiplier bounds.")
    if not checks["driver_stability_ok"]:
        failed = [k for k, v in stability.items() if v < min_driver_stability]
        failures.append(f"Applied driver stability below {min_driver_stability:.0%} for: {', '.join(sorted(failed))}.")
    if not checks["multiplier_range_ok"]:
        failed = [k for k, v in ranges.items() if v > max_multiplier_range]
        failures.append(f"Deterministic multiplier range above {max_multiplier_range:.2f} for: {', '.join(sorted(failed))}.")

    return {
        "ok": all(checks.values()),
        "checks": checks,
        "summary": {
            "rows": total,
            "hard_fails": hard_fails,
            "apply_rate": apply_rate,
            "warning_over_5": warning_over_5,
            "multiplier_failures": multiplier_failures,
        },
        "driver_stability": stability,
        "multiplier_ranges": ranges,
        "failures": failures,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate M15 release gates from eval JSONL results.")
    parser.add_argument("--results", default="evals/results.jsonl", help="Path to eval JSONL from evals.run_evals.")
    parser.add_argument("--min-apply-rate", type=float, default=0.98)
    parser.add_argument("--min-driver-stability", type=float, default=0.8)
    parser.add_argument("--max-multiplier-range", type=float, default=0.3)
    parser.add_argument("--non-shock-min", type=float, default=0.2)
    parser.add_argument("--non-shock-max", type=float, default=3.0)
    parser.add_argument("--shock-max", type=float, default=8.0)
    args = parser.parse_args()

    rows = _load_jsonl(args.results)
    report = evaluate_release_gate(
        rows,
        min_apply_rate=args.min_apply_rate,
        min_driver_stability=args.min_driver_stability,
        max_multiplier_range=args.max_multiplier_range,
        non_shock_min=args.non_shock_min,
        non_shock_max=args.non_shock_max,
        shock_max=args.shock_max,
    )

    print(json.dumps(report["summary"], indent=2))
    if report["failures"]:
        print("Failures:")
        for msg in report["failures"]:
            print(f"- {msg}")
    raise SystemExit(0 if report["ok"] else 3)


if __name__ == "__main__":
    main()
