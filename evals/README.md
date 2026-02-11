# Evals

Consulting eval set for capacity/utilization/day-rate scenario QA.

## Files
- `evals/data/consulting_eval_questions_answers.csv`: source dataset
- `evals/load_evalset.py`: CSV loader and schema checks
- `evals/generate_answer.py`: system-under-test hook
- `evals/grader_prompt.md`: grader rubric prompt
- `evals/grader.py`: LLM grader (score 0-3 + tags + suggested fixes)
- `evals/run_consulting_evals.py`: end-to-end consulting eval runner

## Quick start

```bash
poetry run python -m evals.load_evalset
```

Optional custom CSV path:

```bash
poetry run python -m evals.load_evalset --csv evals/data/consulting_eval_questions_answers.csv
```

The loader validates:
- required columns: `id`, `question`, `expected_answer`
- unique IDs
- non-empty `question` and `expected_answer`

## Run consulting evals

```bash
poetry run python -m evals.run_consulting_evals --n 1 --out evals/out
```

PR-style smoke mode (no external LLM calls):

```bash
EVALS_SMOKE_MODE=1 poetry run python -m evals.run_consulting_evals --n 1 --out evals/out
```

Outputs:
- `evals/out/results.jsonl`
- `evals/out/summary.json`
- `evals/out/failures.jsonl`

## Generate qualitative review report

```bash
poetry run python -m evals.report --results evals/out/results.jsonl --out evals/out/report.md
```

Report includes:
- worst 10 rows
- repeated low-score tags
- question / expected answer / model summary side-by-side
