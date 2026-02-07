from evals.assistant_v3_eval import EvalCase
from evals.run_evals import run_evals, write_jsonl


def test_run_evals_writes_rows(tmp_path):
    rows = run_evals(
        cases=[
            EvalCase(
                case_id="QX1",
                question="reduce costs by 10%",
                expected_driver="cost_target",
                expected_answer_summary="",
                expected_params={},
                assumptions_to_mention="",
                must_include_checks="",
            )
        ],
        n=1,
    )
    assert len(rows) == 1
    assert rows[0]["id"] == "QX1"
    assert "hard_fail" in rows[0]
    assert "warning_summary_count" in rows[0]

    out = tmp_path / "results.jsonl"
    path = write_jsonl(rows, out)
    assert path.exists()
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
