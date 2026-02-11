from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


DEFAULT_EVALSET_PATH = Path("evals/data/consulting_eval_questions_answers.csv")
REQUIRED_COLUMNS = ("id", "question", "expected_answer")


@dataclass(frozen=True)
class EvalRow:
    id: str
    question: str
    expected_answer: str


def _clean(value: str | None) -> str:
    if value is None:
        return ""
    return value.strip()


def _require_columns(fieldnames: Iterable[str] | None) -> None:
    cols = set(fieldnames or [])
    missing = [col for col in REQUIRED_COLUMNS if col not in cols]
    if missing:
        raise ValueError(f"Missing required column(s): {', '.join(missing)}")


def load_evalset(path: str | Path = DEFAULT_EVALSET_PATH) -> list[EvalRow]:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Eval CSV not found: {csv_path}")

    rows: list[EvalRow] = []
    seen_ids: set[str] = set()
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        _require_columns(reader.fieldnames)
        for line_no, raw in enumerate(reader, start=2):
            item_id = _clean(raw.get("id"))
            question = _clean(raw.get("question"))
            expected = _clean(raw.get("expected_answer"))
            if not item_id:
                raise ValueError(f"Row {line_no}: id is empty")
            if item_id in seen_ids:
                raise ValueError(f"Duplicate id: {item_id}")
            if not question:
                raise ValueError(f"Row {line_no}: question is empty")
            if not expected:
                raise ValueError(f"Row {line_no}: expected_answer is empty")
            seen_ids.add(item_id)
            rows.append(EvalRow(id=item_id, question=question, expected_answer=expected))

    return rows


def _main() -> None:
    parser = argparse.ArgumentParser(description="Load consulting eval dataset.")
    parser.add_argument(
        "--csv",
        dest="csv_path",
        default=str(DEFAULT_EVALSET_PATH),
        help="Path to consulting eval CSV.",
    )
    args = parser.parse_args()
    rows = load_evalset(args.csv_path)
    print(f"Loaded {len(rows)} rows from {args.csv_path}")
    for item in rows[:3]:
        print(f"{item.id}: {item.question}")


if __name__ == "__main__":
    _main()
