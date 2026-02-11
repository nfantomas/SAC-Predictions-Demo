from __future__ import annotations

from pathlib import Path

import pytest

from evals.load_evalset import load_evalset


def _write_csv(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def test_load_evalset_smoke_count() -> None:
    rows = load_evalset("evals/data/consulting_eval_questions_answers.csv")
    assert len(rows) == 25
    assert rows[0].id
    assert rows[0].question
    assert rows[0].expected_answer


def test_load_evalset_missing_column_raises(tmp_path: Path) -> None:
    csv_path = tmp_path / "bad.csv"
    _write_csv(
        csv_path,
        "id,question\n1,hello\n",
    )
    with pytest.raises(ValueError, match="Missing required column"):
        load_evalset(csv_path)


def test_load_evalset_duplicate_id_raises(tmp_path: Path) -> None:
    csv_path = tmp_path / "dup.csv"
    _write_csv(
        csv_path,
        "id,question,expected_answer\n1,q1,a1\n1,q2,a2\n",
    )
    with pytest.raises(ValueError, match="Duplicate id: 1"):
        load_evalset(csv_path)
