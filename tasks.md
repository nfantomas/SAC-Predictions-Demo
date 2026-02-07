# Tasks: Stabilize single-step AI Scenario Assistant (V3) and make validation fail-open

## Goal
Improve consistency and reliability of **single-step** V3 scenario generation using Anthropic Opus, while keeping the **existing output JSON schema unchanged**.  
Key outcomes:
- Deterministic-ish outputs (much less run-to-run variance).
- Fewer “crazy” trajectories (e.g., 100x costs), fewer blocked responses.
- Guardrails become **helpful (clamp + warn)** rather than blocking for common queries.
- Clear, concise warning summaries in UI (≤ 5), with full detail available.

## Non-goals
- Do **not** reintroduce 2-step / 1.5-step pipeline.
- Do **not** change the output schema (keys/structure must remain identical).
- Do **not** add new scenario model parameters; use existing parameters.

---

## M15-01 — Make LLM calls as deterministic as possible
### Description
Reduce randomness from the model call itself so repeated runs of the same prompt yield similar JSON.

### Implementation
- In Anthropic client call:
  - Set `temperature = 0`.
  - If available, set `top_p = 1`.
  - Ensure `max_tokens` is sufficient to avoid truncation (truncation causes JSON repair drift).
  - Ensure you do **not** combine multiple conflicting system prompts; use a single system instruction block (or merge into one).

### Definition of Done
- Running the same question 10 times produces:
  - No truncation / incomplete JSON.
  - ≥ 8/10 runs choose the same `suggested_driver`.
  - Parameter magnitudes are within a narrow band (no “sometimes tiny, sometimes huge” shifts).

### QA / Checks
- Run the existing harness 10 times for:
  - “If sick leave increases by 1.5 days…”
  - “keep costs at current levels, what happens to FTEs?”
  - “reduce costs by 10% with no layoffs”
- Compare outputs: driver choice and 10-year multiplier should not swing wildly.

---

## M15-02 — Prompt hardening: explicit units, minimal-knob guidance by driver, built-in self-consistency
### Description
The biggest sources of “nonsense” are unit ambiguity (e.g., 5 vs 0.05) and overuse of knobs. Improve the prompt to:
1) eliminate unit ambiguity,
2) encourage sparse parameterization,
3) require internal consistency checks.

### Implementation
**A) Units (critical)**
- Add a prominent rule near the top:
  - “All percentages are decimals: 0.05 = 5%. Never output 5 for 5%.”
- Add 2–3 explicit examples inside the prompt:
  - `beta_multiplier: 1.05` means +5% variable cost.
  - `cost_target_pct: -0.10` means -10% target.
  - `growth_delta_pp_per_year: -0.02` means -2 percentage points per year (in decimal form).

**B) Minimal parameterization (soft driver templates)**
- Without changing schema, add “preferred minimal set” guidance (soft rules):
  - If driver=`cost_target`: primarily set `cost_target_pct`, timing/ramp fields; keep growth/drift near 0 unless user explicitly asks.
  - If driver=`fte`: set `fte_delta_abs` or `fte_delta_pct`, timing/ramp fields; only set `beta_multiplier` if wage/price assumption changes.
  - If driver=`cost`: use `impact_mode` + `impact_magnitude` or growth deltas; avoid cost_target/fte deltas unless the user explicitly requests.

**C) Self-consistency requirement (no schema change)**
- Instruct model that `rationale.sanity_checks.ten_year_multiplier_estimate` must be a **number** and should match the narrative magnitude.
- Require the model to mention any clamps in `safety.adjustments` (already in schema).

### Definition of Done
- For a fixed set of 20 eval questions:
  - ≥ 90% of responses use decimal units correctly (no “5” for 5%).
  - Responses set only a small subset of params (most remain 0/null) unless the question demands complexity.
  - Outputs are valid JSON matching schema every time.

### QA / Checks
- Regression checklist:
  - `abs(cost_target_pct) <= 0.5` and is decimal.
  - `abs(growth_delta_pp_per_year) <= 0.5` and is decimal.
  - `ten_year_multiplier_estimate` parses as float.

---

## M15-03 — Validator: “helpful not blocking” (fail-open), with strict hard-invariant errors only
### Description
Current guardrails often block realistic questions. Convert most “errors” into clamp+warn, and only block on true invariants.

### Implementation
**A) Keep as hard errors only**
- NaN/Inf values.
- Negative cost anywhere in produced series.
- `alpha > cost_at_t0` (implies negative variable portion).
- Missing required fields / invalid schema / cannot parse JSON.

**B) Convert these to clamp + warning**
- 10-year multiplier / CAGR caps → clamp growth/impact to safe range and warn.
- Monthly change exceeding cap → smooth/clamp and warn.
- “Projection multiplier out of bounds” → do not error; apply safe clamp and warn.

**C) Warning summarization**
- Deduplicate repeated clamp messages (same field + same clamp).
- Provide a short summary (≤ 5 bullets) and keep full details in logs/expander.

### Definition of Done
- For all eval questions:
  - The system returns an answer (applies a scenario) unless it violates hard invariants.
  - No “Validation failed … out of bounds” errors for common asks.
  - User sees ≤ 5 warning bullets by default.

### QA / Tests
- Automated run across eval CSV:
  - Hard failures ≤ 2% (and only invariant violations).
  - Summary warnings ≤ 5 each run.
- Unit tests for: clamp->warning; warning dedup; fail-open path.

---

## M15-04 — Auto-normalize percent-as-whole-number (single warning)
### Description
Even with prompt improvements, occasional percent-as-whole-number will occur. Normalize automatically.

### Implementation
For percent-like fields:
- `impact_magnitude`, `growth_delta_pp_per_year`, `drift_pp_per_year`, `event_growth_delta_pp_per_year`, `cost_target_pct`, `fte_delta_pct`
If `abs(value) > 1.5`:
- divide by 100 (assume percent input)
- add **one** warning: “Normalized 5 → 0.05 assuming percent units.”
Ensure normalization is idempotent (doesn’t re-normalize).

### Definition of Done
- If model outputs `5` where `0.05` is expected, the system:
  - normalizes,
  - warns once,
  - and continues.

### QA / Tests
- Unit tests:
  - input: `cost_target_pct=10` → normalized to `0.10`, warning emitted once.
  - input: `growth_delta_pp_per_year=-8` → normalized to `-0.08`.

---

## M15-05 — Universal capacity/productivity intent heuristic (prompt-level)
### Description
Many workforce questions are capacity-related (sick leave, 4-day week, utilization targets, efficiency gains). We want general guidance that works across the eval set.

### Implementation (prompt only; no schema change)
- Add rule:
  - “If the question is about maintaining output/capacity given reduced effective hours/productivity, default to **FTE driver** unless the user explicitly requests cost-only.”
- Add examples:
  - “sick leave ↑”, “4-day week”, “utilization ↓”, “productivity ↑” → usually `fte`.
  - “cap total cost growth at X%” → `cost_target`.

### Definition of Done
- Driver choice is stable for capacity-style questions (≥ 8/10 repeats match expected).

### QA
- Add a small driver-selection regression set (10 prompts) and assert expected driver.

---

## M15-06 — UI: show safety adjustments cleanly (≤ 5 summary + details expander)
### Description
Even with fail-open, users must understand what got adjusted.

### Implementation
- In Streamlit:
  - Banner when clamps/normalizations occurred: “Applied with safety adjustments”.
  - Show ≤ 5 bullet warnings.
  - “Show details” expander with the full clamp/normalize log.
- Ensure chart overlay uses **post-normalization, post-validation** params.

### Definition of Done
- When a clamp happens:
  - user sees short summary,
  - can expand for details,
  - chart uses corrected values.

### QA
- Force a normalization case (e.g., `cost_target_pct=10`) and verify banner + chart correctness.

---

## M15-07 — Eval-based regression harness for stability (N-runs per prompt)
### Description
Use your eval CSV to detect regressions and measure stability, not only correctness.

### Implementation
- Add script `evals/run_evals.py`:
  - loads `eval_questions_answers.csv`,
  - runs N times per question (default N=3),
  - stores: suggested_driver, key params, ten_year_multiplier_estimate, warning summary count, hard_fail flag
  - writes `evals/results.jsonl`.

### Definition of Done
- Can run: `python -m evals.run_evals --n 3`
- Produces results file with per-run metrics.

### QA
- Sanity check: no crashes; hard failures ≤ 2%.
- Spot check: for repeated runs, driver stable for most prompts.

---

## Release Gate (acceptance criteria)
A build is acceptable when:
1) **Schema compliance:** 100% outputs validate against schema (no extra keys, valid JSON).
2) **Fail-open:** ≥ 98% of prompts produce an applied scenario (hard errors only on invariants).
3) **Stability:** For 10 key prompts run 10 times:
   - ≥ 8/10 identical `suggested_driver`
   - `ten_year_multiplier_estimate` range ≤ 0.3 (tunable threshold)
4) **Warnings UX:** summary ≤ 5 bullets, with details available.
5) **No extreme explosions:** 10-year multiplier stays within [0.2x, 3.0x] after clamps.

