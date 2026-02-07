# tasks.md — LLM Evals for Scenario Assistant (Non-binary, 0–3 scoring)

## Purpose
Create a **simple, repeatable eval harness** to assess the quality of the Scenario Assistant outputs (single-step V3), using the prepared dataset of sample questions + expected answer shape. Evals must:
- run **automatically** (LLM-as-judge)
- produce **4-level scores**: `0,1,2,3`
- be **diagnostic**, not just pass/fail (surface why a score was given and what to improve)
- be **stable enough** to compare changes across iterations (prompt/guardrails/UI/apply logic)

**Input dataset:** `eval_questions_answers.csv` (generated earlier).

---

## Status legend
- `NOT STARTED`
- `IN PROGRESS`
- `IN QA`
- `BLOCKED`
- `DONE`

---

## Milestone M-EVAL — Evaluation System (LLM-graded)
**Milestone goal:** One command runs evals end-to-end and produces a scored report + actionable breakdown.

### M-EVAL Task List

#### M-EVAL-01 — Define eval rubric (0–3) + scoring guidelines (shared contract)
- **Status:** NOT STARTED
- **Owner (Dev):** AI/Backend Dev
- **QA:** QA Engineer
- **Description:**
  Create a clear rubric for judging model answers against expectations from `eval_questions_answers.csv`. The rubric must be:
  - **non-binary** with four levels (0–3)
  - consistent across scenario types (cost, fte, cost_target, mix_shift, etc.)
  - explicit about what counts as “messy but good reasoning” (score 1) vs “reasonable” (score 2)
  - aligned to the demo’s business logic (Cost = α + β·FTE; fixed share ~20%; baseline growth ~6% YoY; inflation ~3% YoY)
- **Deliverable:** `evals/rubric.md`
- **Definition of done:**
  - Rubric defines scores **0,1,2,3** with:
    - **Required conditions**
    - **Common failure modes**
    - **Examples** for at least 5 prompt types (cost constraint, FTE reduction, shock, hiring freeze, mix shift)
  - Rubric clarifies how to treat:
    - missing details (should the judge penalize vs allow)
    - “ask clarification” answers (when they are acceptable)
    - guardrail clamps (when they are acceptable)
  - Rubric is referenced by the judge prompt (M-EVAL-03) verbatim or summarized precisely.
- **What to test (QA):**
  - Rubric review against 10 random questions: QA can independently score and the rubric yields consistent outcomes (low ambiguity).
  - Ensure rubric includes a section **“how to score clarifications”**.

---

#### M-EVAL-02 — Create eval dataset loader + normalization (CSV → eval cases)
- **Status:** NOT STARTED
- **Owner (Dev):** Backend Dev
- **QA:** QA Engineer
- **Description:**
  Implement a loader that reads `eval_questions_answers.csv` and yields a structured `EvalCase` object used by the harness.
  Required fields:
  - `id`, `question`
  - `expected_driver`
  - `expected_answer_summary`
  - `expected_params_json`
  - `assumptions_to_mention`
  - `must_include_checks`
- **Deliverable:** `evals/dataset.py` + `evals/types.py`
- **Definition of done:**
  - `EvalCase` is a dataclass/pydantic model with validation.
  - Loader fails fast with actionable error if a required column is missing.
  - `expected_params_json` is parsed into an object; parse errors are reported with case id.
  - Supports filtering by ids (e.g., `--ids Q01,Q02`) and sampling (e.g., `--limit 20`).
- **What to test (QA):**
  - Unit tests:
    - loads the CSV and returns correct count
    - malformed JSON in `expected_params_json` → clear error includes case id
    - `--ids` filter returns correct subset

---

#### M-EVAL-03 — Implement LLM-as-judge prompt (uses rubric + expected outputs) and scoring (0–3)
- **Status:** NOT STARTED
- **Owner (Dev):** AI Dev
- **QA:** QA Engineer
- **Description:**
  Build a judge that scores a **candidate answer** produced by the app (LLM output + applied scenario summary) against the expected content.
  Judge inputs per case must include:
  - user question
  - model output JSON (driver + params + explanation)
  - short computed outcomes (e.g., year-1/5/10 multipliers vs baseline; direction of cost/FTE change)
  - expected fields from CSV (`expected_driver`, `expected_answer_summary`, `expected_params_json`, checks)
  - rubric text
- **Deliverable:** `evals/judge.py` + `evals/judge_prompt.md`
- **Definition of done:**
  - Judge returns strict JSON:
    ```json
    {
      "score": 0|1|2|3,
      "reasons": ["..."],
      "missing_or_wrong": ["..."],
      "strengths": ["..."],
      "suggested_fix": "one short suggestion",
      "flags": {
        "unit_error_suspected": true|false,
        "driver_mismatch": true|false,
        "unsafe_magnitude": true|false
      }
    }
    ```
  - Judge enforces score meaning:
    - **0**: wrong driver or wrong direction / nonsensical
    - **1**: messy but shows correct reasoning, incomplete/mistuned params
    - **2**: reasonable and mostly aligned, minor issues
    - **3**: correct driver + plausible params + clear rationale + meets must-include checks
  - Judge explicitly checks “must_include_checks” and uses them to justify score.
  - The judge prompt includes **unit guidance** (decimals vs percent) so it can flag suspected unit errors.
- **What to test (QA):**
  - Unit tests with *golden* candidate answers (handcrafted) to ensure judge returns expected score:
    - one clearly wrong (expect 0)
    - one messy but correct reasoning (expect 1)
    - one reasonable (expect 2)
    - one ideal (expect 3)
  - Contract test: judge output must be valid JSON and contain all keys.

---

#### M-EVAL-04 — Build eval runner to execute the app logic and collect candidate outputs
- **Status:** NOT STARTED
- **Owner (Dev):** Backend Dev
- **QA:** QA Engineer
- **Description:**
  Implement an eval runner that:
  1) loads cases
  2) calls the **same code path** as the Streamlit assistant (prompt → LLM → parse → normalize → validate → apply)
  3) captures:
     - raw LLM output
     - parsed suggestion object
     - validation warnings/clamps
     - computed outcomes summary vs baseline
  4) invokes judge
  5) writes a report
- **Deliverable:** `evals/run.py` + CLI entry `python -m evals.run`
- **Definition of done:**
  - Command runs:
    - `python -m evals.run --input eval_questions_answers.csv --model <candidate_model> --judge_model <judge_model> --out reports/eval_report.json`
  - Uses environment config for API keys; secrets never printed.
  - Runner has `--dry-run` mode that uses stored candidate outputs (no API calls).
  - Produces per-case records with:
    - `case_id`, `score`, `reasons`, `flags`
    - candidate `scenario_driver`
    - warning summary count
    - key metrics (year-1/5/10 multipliers vs baseline)
- **What to test (QA):**
  - Integration (no real LLM): run with `--dry-run` and fixtures → report produced.
  - Integration (real LLM optional): run `--limit 3` end-to-end and confirm no crashes.

---

#### M-EVAL-05 — Reporting: summary table + failure clustering (where to improve)
- **Status:** NOT STARTED
- **Owner (Dev):** Backend Dev
- **QA:** QA Engineer
- **Description:**
  Convert raw per-case results into actionable insights:
  - distribution of scores
  - top recurring failure reasons
  - driver mismatch rate
  - suspected unit error rate
  - unsafe magnitude flags
- **Deliverable:** `evals/report.py` producing:
  - `reports/eval_report.json` (full)
  - `reports/eval_summary.csv` (flat table)
  - `reports/eval_summary.md` (human-readable)
- **Definition of done:**
  - `eval_summary.md` includes:
    - score histogram
    - worst 10 cases (score 0/1) with reasons
    - grouped failure categories with counts (e.g., unit errors, driver mismatch, unrealistic magnitude, missing assumptions)
    - 3–5 prioritized next improvements (auto-generated or templated)
- **What to test (QA):**
  - Run report generator on fixture results and verify outputs created and non-empty.
  - Ensure markdown contains the required sections.

---

#### M-EVAL-06 — CI-friendly “regression gate” (optional but recommended)
- **Status:** NOT STARTED
- **Owner (Dev):** DevOps Dev
- **QA:** QA Lead
- **Description:**
  Add a lightweight regression check that can run in CI without calling real LLMs by using stored candidate outputs + stored judge outputs.
- **Deliverable:** `tests/test_eval_regression.py` + `evals/fixtures/*`
- **Definition of done:**
  - CI job runs eval regression tests offline.
  - Fails if:
    - schema breaks
    - reporting breaks
    - warning summarizer exceeds max
  - Does NOT require network or API keys.
- **What to test (QA):**
  - On clean checkout: `pytest -q` passes with no env vars set.

---

## Milestone Exit Criteria (M-EVAL)
- One command runs evals (dry-run at minimum) and outputs `eval_summary.md` + `eval_summary.csv`.
- Scores are 0–3 with clear reasons and flags.
- The process highlights **actionable** improvement areas (prompt vs validation vs apply logic).
- Offline/fixture mode exists for repeatability.

---

## Notes / Guardrails for LLM-as-judge
- Keep judge deterministic by:
  - temperature low (e.g., 0–0.2)
  - strict JSON output
  - rubric included
- Judge must not “invent” missing facts; it should only compare:
  - question
  - expected content
  - candidate output
  - computed outcomes summary

