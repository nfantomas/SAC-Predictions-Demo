from __future__ import annotations

import csv
import json
from pathlib import Path

from evals.run_consulting_evals import _stub_generate_answer, _stub_grade_answer, run_consulting_evals


def _write_eval_csv(path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["id", "question", "expected_answer"])
        writer.writeheader()
        writer.writerow(
            {
                "id": "Q01",
                "question": "reduce costs by 10% without layoffs",
                "expected_answer": "Use cost target with no-layoff caveat.",
            }
        )


def test_run_consulting_evals_smoke(monkeypatch, tmp_path: Path):
    from evals.load_evalset import load_evalset
    from evals.run_consulting_evals import _safe_write_json, _safe_write_jsonl

    csv_path = tmp_path / "consulting.csv"
    _write_eval_csv(csv_path)
    rows = load_evalset(csv_path)

    def fake_generate_answer(_question: str):
        return {
            "error_type": "",
            "error_message": "",
            "model_output_json": {"safety": {"adjustments": ["Clamped impact_magnitude to bounds."]}},
            "applied_params": {"driver": "cost_target", "cost_target_pct": -0.1, "lag_months": 6},
            "summary_text": "Cost target of -10% over a moderate ramp.",
            "key_metrics": {
                "driver": "cost_target",
                "warnings_count": 1,
                "deterministic_ten_year_multiplier": 0.9,
            },
        }

    def fake_grade_answer(**_kwargs):
        return {
            "score": 2,
            "reasoning": "Mostly correct, minor assumptions.",
            "tags": ["driver_selection", "clarity"],
            "suggested_fix": ["State assumptions explicitly."],
        }

    monkeypatch.setattr("evals.run_consulting_evals.generate_answer", fake_generate_answer)
    monkeypatch.setattr("evals.run_consulting_evals.grade_answer", fake_grade_answer)

    results, failures, summary = run_consulting_evals(rows, n=1)
    assert len(results) == 1
    assert len(failures) == 0
    assert summary["mean_score"] == 2.0
    assert summary["score_histogram"]["2"] == 1
    assert results[0]["model_driver"] == "cost_target"
    assert results[0]["warnings_count"] == 1

    out_dir = tmp_path / "out"
    _safe_write_jsonl(out_dir / "results.jsonl", results)
    _safe_write_json(out_dir / "summary.json", summary)
    _safe_write_jsonl(out_dir / "failures.jsonl", failures)
    assert (out_dir / "results.jsonl").exists()
    assert (out_dir / "summary.json").exists()
    assert (out_dir / "failures.jsonl").exists()

    summary_payload = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
    assert "OPENAI_API_KEY" not in json.dumps(summary_payload)


def test_run_consulting_evals_with_stub_mode(tmp_path: Path):
    from evals.load_evalset import load_evalset

    csv_path = tmp_path / "consulting.csv"
    _write_eval_csv(csv_path)
    rows = load_evalset(csv_path)
    results, failures, summary = run_consulting_evals(
        rows,
        n=1,
        answer_fn=_stub_generate_answer,
        grader_fn=_stub_grade_answer,
    )
    assert len(results) == 1
    assert not failures
    assert results[0]["model_driver"] in {"cost", "fte", "cost_target"}
    assert summary["mean_score"] == 2.0
