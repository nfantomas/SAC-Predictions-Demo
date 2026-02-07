# Assistant V3 Evals

Run evaluation questions from `eval_questions_answers.csv` against the one-step V3 assistant.

## Quick run

```bash
poetry run python -m demo.assistant_v3_eval --csv eval_questions_answers.csv
```

The command runs an LLM connectivity preflight first. If preflight fails, no eval calls are made.
It also raises LLM runtime limits for eval stability by default:
- timeout: at least `900s`
- retries: at least `4`
- max tokens: at least `4096`

## Limit + export details

```bash
poetry run python -m demo.assistant_v3_eval --csv eval_questions_answers.csv --limit 10 --out data/cache/assistant_v3_eval_results.csv
```

To override limits explicitly for a run:

```bash
poetry run python -m demo.assistant_v3_eval --csv eval_questions_answers.csv --id Q02 --llm-timeout-seconds 1200 --llm-max-retries 6 --llm-max-tokens 8192
```

## One-question bug-fix loop

Run exactly one case by id and use the exit code for pass/fail:

```bash
poetry run python -m demo.assistant_v3_eval --csv eval_questions_answers.csv --id Q01
```

- Exit code `0`: the selected case(s) passed.
- Exit code `3`: at least one selected case did not pass.

Multiple ids are supported:

```bash
poetry run python -m demo.assistant_v3_eval --csv eval_questions_answers.csv --id Q01,Q07,Q21
```

## Troubleshooting preflight

- `llm_dns_error`: DNS cannot resolve `api.anthropic.com` (or your configured base URL). Check internet/DNS and `ANTHROPIC_API_BASE`.
- `llm_timeout`: network path exists but timed out. Check firewall/proxy; optionally increase `LLM_TIMEOUT_SECONDS`.
- `llm_connection_refused`: endpoint blocked/refused. Check proxy/firewall and API base URL.
- `llm_ssl_error`: TLS/certificate issue (often proxy SSL interception).
- `llm_http_401_invalid_key`: invalid or expired `ANTHROPIC_API_KEY`.

To bypass preflight (for debugging only):

```bash
poetry run python -m demo.assistant_v3_eval --csv eval_questions_answers.csv --skip-preflight
```

## Output

Each round now supports two artifacts:

1. **Eval log** (CSV): all questions with answer text and timing.
2. **Scorecard** (Markdown): round summary + per-question scoring stats (readable).
3. **Scorecard** (JSON): same data in machine-readable format.

When `--out` is provided, it writes:

- log CSV to `--out`
- scorecard Markdown to `<out_stem>_scorecard.md`
- scorecard JSON to `<out_stem>_scorecard.json`
- benchmark JSON to `evals/benchmark/assistant_v3_eval_benchmark.json` (tracked in git)

You can also set explicit paths:

```bash
poetry run python -m demo.assistant_v3_eval \
  --csv eval_questions_answers.csv \
  --log-out data/cache/assistant_v3_eval_log.csv \
  --scorecard-md-out data/cache/assistant_v3_eval_scorecard.md \
  --scorecard-out data/cache/assistant_v3_eval_scorecard.json
```

Benchmark compare (Markdown shows `current / benchmark` on numeric fields):

```bash
poetry run python -m demo.assistant_v3_eval \
  --csv eval_questions_answers.csv \
  --log-out data/cache/assistant_v3_eval_results.csv \
  --benchmark-in evals/benchmark/assistant_v3_eval_benchmark.json \
  --benchmark-out evals/benchmark/assistant_v3_eval_benchmark.json
```

Scorecard uses `answer_score`:
- `0`: no match
- `1`: really messy
- `2`: okayish
- `3`: decent match

`answer_score` is LLM-graded during CLI eval runs (`demo.assistant_v3_eval`), with automatic fallback to heuristic scoring only if grading call fails.
