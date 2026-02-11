# tasks.md — Consulting Demo Evals (Capacity / Utilization / MD Rate)

## Objective
Implement a **simple, repeatable evaluation pipeline** for the consulting-sector version of the demo (capacity + utilization + MD rate + fixed costs), using the prepared CSV:
- Input dataset: `consulting_eval_questions_answers.csv`
- Evals scored by an LLM on a **4-level rubric**:
  - **0 — Wrong** (incorrect driver, incorrect math/logic, unsafe/extreme, or ignores constraints)
  - **1 — Messy but good reasoning** (directionally right, but unclear/rambling or missing key business implications)
  - **2 — Reasonable** (mostly correct, minor gaps or mild inconsistency; acceptable for demo)
  - **3 — Correct** (clear, consistent, business-ready, numbers/assumptions aligned, no hallucinated extremes)

Evals must help us:
1) quantify quality (score distribution),
2) spot systematic failure modes (driver choice, units, utilization math, fixed/variable logic, timing),
3) generate actionable improvements (prompt/validator/UI).

## Constraints / Non-goals
- Keep evals **lightweight** (no heavy infra, no complex dashboards required).
- **No binary** pass/fail; must store 0–3 + reasoning.
- Must be runnable locally (Poetry) and in CI.
- Do not require SAC connectivity (use cached/fixture series).
- Do not change the model output schema; evaluate what the app produces.

---

## Milestone M16 — Evals for Consulting Demo

### M16-01 — Add eval dataset to repo + loader
- **Status:** DONE
- **Owner (Dev):** Backend Dev
- **QA:** QA Engineer
- **Description:** Add the consulting eval CSV to the repo and implement a small loader that normalizes the schema for the eval runner.
- **Deliverable:**
  - `evals/data/consulting_eval_questions_answers.csv` (checked in)
  - `evals/load_evalset.py` (loads CSV → list of {id, question, expected_answer})
  - `evals/README.md` describing how to run evals
- **Definition of done:**
  - Loader validates columns exist: `id`, `question`, `expected_answer`
  - IDs are unique; questions are non-empty; expected answers non-empty
  - Running `python -m evals.load_evalset` prints count and first 3 ids/questions
- **What to test (QA):**
  - Unit test: malformed CSV (missing column) → clear error
  - Unit test: duplicate ids → clear error
  - Smoke: loader prints correct count (=25)

---

### M16-02 — Implement deterministic “answer generator” hook (system under test)
- **Status:** DONE
- **Owner (Dev):** App Dev
- **QA:** QA Engineer
- **Description:** Provide a single function that produces the app’s “final answer” for a question, in a deterministic-ish manner, so evals can call it consistently.
  - This should call the **same pipeline** as the UI “Scenario Assistant” (single-step V3), including: prompt build → LLM call → parse → normalize → validate (fail-open) → apply-to-series.
- **Deliverable:**
  - `evals/generate_answer.py` with `generate_answer(question: str) -> dict`
  - Returned dict must include:
    - `model_output_json` (raw structured JSON from assistant, post-parse)
    - `applied_params` (post-normalization + validation)
    - `summary_text` (short CFO-style explanation shown to user, can be from `rationale.summary`)
    - `key_metrics` (e.g., ten_year_multiplier_estimate, driver, warnings_count)
- **Definition of done:**
  - For any input question, function returns a dict or a “clarification required” result (but should prefer fail-open)
  - Uses deterministic settings (temperature=0, etc.) as configured in app
  - Does **not** require Streamlit runtime (pure python module)
- **What to test (QA):**
  - Unit test: returns required keys
  - Unit test: JSON parse failures are handled (retry/repair or fail-open fallback) and produce a structured “error_type”
  - Golden test: run on 3 sample questions and assert stable `suggested_driver`

---

### M16-03 — LLM grader prompt + rubric (0–3) for consulting answers
- **Status:** DONE
- **Owner (Dev):** ML/Prompt Dev
- **QA:** QA Lead
- **Description:** Create a grader prompt that compares:
  - **Question**
  - **Expected answer** (from CSV)
  - **Model produced output** (summary + params + key metrics)
  and returns a JSON grade with score 0–3 and concise rationale.
- **Deliverable:**
  - `evals/grader_prompt.md`
  - `evals/grader.py` that calls the grader LLM and returns:
    - `score` (0–3 int)
    - `reasoning` (<= 8 sentences)
    - `tags` (list: e.g., `["units", "driver_selection", "utilization_math"]`)
    - `suggested_fix` (1–2 bullets)
- **Definition of done:**
  - Grader output is **strict JSON** (no markdown/code fences)
  - Grader is stable at temperature=0
  - Tags are from a fixed allowlist:
    - `driver_selection`, `units`, `timing`, `fixed_variable_logic`, `utilization_math`,
      `rate_math`, `capacity_logic`, `safety_extremes`, `clarity`, `missing_assumptions`
- **What to test (QA):**
  - Unit test: grader rejects non-JSON (repair or retry) and still returns JSON
  - Unit test: score is int in [0,3]
  - Spot check: 5 eval rows manually reviewed to ensure rubric aligns with business expectations

---

### M16-04 — Eval runner (N runs, aggregates, artifacts)
- **Status:** DONE
- **Owner (Dev):** Backend Dev
- **QA:** QA Engineer
- **Description:** Build a runner that:
  1) loads the eval CSV,
  2) generates model answers,
  3) grades them with the LLM grader,
  4) writes results to disk + prints summary metrics.
- **Deliverable:**
  - `evals/run_consulting_evals.py` runnable as module:
    - `python -m evals.run_consulting_evals --n 3 --out evals/out/`
  - Output artifacts:
    - `results.jsonl` (one line per (question, run))
    - `summary.json` (aggregate stats)
    - `failures.jsonl` (any hard failures / exceptions)
- **Definition of done:**
  - Runner supports `--n` repeats per question (default 1; use 3 for stability)
  - Summary prints:
    - mean score, score histogram, % hard failures
    - top 10 most common tags
    - top 5 lowest-scoring questions (with ids)
  - Results contain:
    - eval id, question, expected_answer
    - model driver + key params subset
    - warnings count + clamp summary
    - grader score + tags + reasoning
- **What to test (QA):**
  - Smoke run with `--n 1` finishes and produces all files
  - Determinism check: with temperature=0, driver choice should be mostly stable across `--n 3`
  - Verify no secrets are written to outputs (redact API keys)

---

### M16-05 — CI wiring (nightly + PR smoke)
- **Status:** DONE
- **Owner (Dev):** DevOps Dev
- **QA:** QA Lead
- **Description:** Add a lightweight CI job:
  - On PR: run a **smoke eval** (e.g., 5 questions, n=1) with mocked LLM OR a stub grader.
  - Nightly: full eval run (25 questions, n=1 or n=3 depending on cost).
- **Deliverable:**
  - CI config (GitHub Actions or equivalent)
  - `EVALS_SMOKE_MODE=1` option to:
    - run 5 fixed questions
    - optionally use a deterministic stub grader for PRs
- **Definition of done:**
  - PR checks run in <10 minutes (smoke)
  - Nightly produces artifacts stored as build outputs
- **What to test (QA):**
  - Open PR: CI runs smoke eval job and uploads artifacts
  - Nightly job is scheduled and runs successfully at least once

---

### M16-06 — Human review loop: “qualitative drill-down” view
- **Status:** DONE
- **Owner (Dev):** App Dev
- **QA:** QA Engineer
- **Description:** Provide a minimal way to inspect results for improvement decisions.
  - Prefer a simple HTML/markdown report or a tiny Streamlit page that reads `results.jsonl`.
- **Deliverable (choose one):**
  - `evals/report.py` generating `evals/out/report.md` (recommended), OR
  - `evals/review_app.py` (Streamlit) to filter by score/tag
- **Definition of done:**
  - A reviewer can quickly see:
    - worst 10 items (score 0/1)
    - repeated failure tags
    - model output + expected answer side-by-side
- **What to test (QA):**
  - Generate report from a sample `results.jsonl` and confirm it renders and includes required sections

---

## Global Definition of Done (M16)
- Running `python -m evals.run_consulting_evals --n 1` produces:
  - `results.jsonl`, `summary.json`, `failures.jsonl` (even if failures is empty)
- Grader returns 0–3 score and tags for every completed run
- Results include enough fields to diagnose issues (driver, utilization/rate reasoning, fixed/variable logic, clamps)
- CI smoke run exists and does not require SAC access

---

## Notes / Guardrails for implementation
- Use deterministic settings for both **answer generator** and **grader** (temperature=0).
- Redact/omit any secrets in logs and output files.
- Keep “expected answers” as qualitative guidance, not exact numeric targets; scoring focuses on:
  - correct lever selection (utilization vs rate vs capacity)
  - correct proportional reasoning (linear scaling)
  - correct fixed-vs-variable intuition
  - sensible timing and magnitude
