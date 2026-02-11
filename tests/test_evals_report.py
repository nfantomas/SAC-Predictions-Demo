from __future__ import annotations

import json
from pathlib import Path

from evals.report import _read_jsonl, build_report


def test_report_contains_required_sections(tmp_path: Path):
    rows = [
        {
            "id": "Q01",
            "question": "q1",
            "expected_answer": "e1",
            "summary_text": "s1",
            "warnings_count": 1,
            "grader": {
                "score": 1,
                "reasoning": "missing assumptions",
                "tags": ["missing_assumptions", "clarity"],
            },
        },
        {
            "id": "Q02",
            "question": "q2",
            "expected_answer": "e2",
            "summary_text": "s2",
            "warnings_count": 0,
            "grader": {
                "score": 3,
                "reasoning": "good",
                "tags": ["driver_selection"],
            },
        },
    ]
    path = tmp_path / "results.jsonl"
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")

    loaded = _read_jsonl(path)
    md = build_report(loaded)
    assert "## Summary" in md
    assert "## Repeated Failure Tags" in md
    assert "## Worst 10 Items" in md
    assert "### Q01" in md
    assert "Expected answer: e1" in md

