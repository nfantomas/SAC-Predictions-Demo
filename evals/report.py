from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List


def _read_jsonl(path: str | Path) -> List[Dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"results.jsonl not found: {p}")
    rows: List[Dict[str, Any]] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def _top_failure_tags(rows: List[Dict[str, Any]], top_n: int = 10) -> List[tuple[str, int]]:
    counter = Counter()
    for row in rows:
        score = int(row.get("grader", {}).get("score", 0))
        if score > 1:
            continue
        tags = row.get("grader", {}).get("tags", [])
        if isinstance(tags, list):
            for tag in tags:
                if isinstance(tag, str):
                    counter[tag] += 1
    return counter.most_common(top_n)


def _worst_items(rows: List[Dict[str, Any]], top_n: int = 10) -> List[Dict[str, Any]]:
    ordered = sorted(
        rows,
        key=lambda r: (
            int(r.get("grader", {}).get("score", 99)),
            -int(r.get("warnings_count", 0)),
            r.get("id", ""),
        ),
    )
    return ordered[:top_n]


def build_report(rows: List[Dict[str, Any]]) -> str:
    total = len(rows)
    low = [r for r in rows if int(r.get("grader", {}).get("score", 0)) <= 1]
    top_tags = _top_failure_tags(rows)
    worst = _worst_items(rows)

    lines: List[str] = []
    lines.append("# Consulting Evals Review Report")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Total rows: {total}")
    lines.append(f"- Low-score rows (0/1): {len(low)}")
    lines.append(f"- Unique question IDs: {len({r.get('id') for r in rows})}")
    lines.append("")
    lines.append("## Repeated Failure Tags")
    lines.append("")
    if not top_tags:
        lines.append("- None")
    else:
        for tag, count in top_tags:
            lines.append(f"- `{tag}`: {count}")
    lines.append("")
    lines.append("## Worst 10 Items")
    lines.append("")
    for row in worst:
        grade = row.get("grader", {})
        lines.append(f"### {row.get('id', '-')}")
        lines.append(f"- Score: `{grade.get('score', '-')}`")
        lines.append(f"- Tags: `{', '.join(grade.get('tags', [])) if isinstance(grade.get('tags'), list) else '-'}`")
        lines.append(f"- Question: {row.get('question', '')}")
        lines.append(f"- Expected answer: {row.get('expected_answer', '')}")
        lines.append(f"- Model summary: {row.get('summary_text', '')}")
        lines.append(f"- Reasoning: {grade.get('reasoning', '')}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate markdown review report from consulting eval results.")
    parser.add_argument("--results", default="evals/out/results.jsonl", help="Path to results.jsonl")
    parser.add_argument("--out", default="evals/out/report.md", help="Output markdown path")
    args = parser.parse_args()

    rows = _read_jsonl(args.results)
    report = build_report(rows)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")
    print(f"Wrote report: {out_path}")


if __name__ == "__main__":
    main()

