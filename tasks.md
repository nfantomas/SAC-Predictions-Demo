# tasks.md — M14 Two-Step AI (Interpreter → Compiler) + Fail-Open Guardrails

## Objective
Guarantee the demo **always returns an answer** for scenario questions (apply or clarify), while increasing reliability and reducing brittle “clamp/invalid” failures by:
- splitting LLM work into **two steps**: **Scenario Interpreter** → **Parameter Compiler**
- keeping the current **V3 scenario engine** (do not delete modeling power), but reducing what the LLM must do in one shot
- changing guardrails to **fail-open**: block only on mathematical invalidity; otherwise **apply + warn + explain**
- adding **unit normalization** (5 → 0.05) and **deduplicated warnings**

## Non-goals (explicit)
- No SAC write-back.
- No new forecasting method changes (only scenario assistant pipeline + validation behavior).
- No UI redesign beyond what’s required to wire the new assistant safely.

## Key principles (to avoid “lost in translation”)
1) **Single source of truth** for schema + defaults: stored in code and exported for prompts.
2) **Golden tests** from real prompts: acceptance suite must prevent regressions.
3) **Deterministic templates first**: LLM is used only where ambiguity remains.
4) **Never crash the app**: all LLM/validation errors must degrade gracefully.

---

# Milestone Exit Criteria (M14)
All must be true:
- For a set of **≥ 25 representative prompts** (provided in `tests/fixtures/sample_prompts.json`), the assistant returns:
  - either an applied scenario, or a single clarifying question (max 1) with `need_clarification=true`
  - **0 unhandled exceptions**
- “Validation failed … out of bounds” does **not** block typical prompts; it is converted into warnings unless mathematically invalid.
- LLM percent/unit mistakes are **normalized** with a clear warning (“normalized 5 → 0.05”).
- CI (or local test run) includes: unit tests + acceptance tests + smoke.

---

## M14-01 — Define ScenarioIntent schema (Interpreter output) + fixtures
- **Status:** NOT STARTED
- **Owner (Dev):** Backend/LLM
- **QA:** QA Engineer

### Description
Create a small, robust **ScenarioIntent** JSON schema that captures user intent, timing, constraints, and severity—**without** requiring the LLM to emit detailed numeric curve parameters.

### Deliverables
- `llm/intent_schema.py` (Pydantic model + `.json_schema()` export)
- `docs/intent_schema.md` with 10 examples
- `tests/fixtures/intent_examples.json` (valid examples)
- `tests/test_intent_schema.py` (schema validation tests)

### ScenarioIntent (required fields)
- `schema_version`: `"intent_v1"`
- `intent_type`: `constraint|shock|policy|target|mix_shift|productivity|attrition|relocation|other`
- `driver`: `auto|cost|fte|cost_target`
- `direction`: `increase|decrease|hold|unknown`
- `magnitude`: `{ "type": "pct|abs|yoy_cap|none", "value": float|null }`
- `timing`: `{ "start": "YYYY-MM", "duration_months": int|null, "ramp_months": int }`
- `constraints`: string[] (allowlist; e.g., `no_layoffs`, `keep_cost_flat`, `keep_fte_flat`)
- `entities`: `{ "regions": string[]|null, "population": "global"|null }`
- `severity`: `operational|stress|crisis`
- `confidence`: `low|medium|high`
- `need_clarification`: bool
- `clarifying_question`: string|null

### Definition of Done
- Schema rejects unknown fields by default (`extra="forbid"`), unless explicitly allowed.
- Every schema field has a clear description and examples (in `docs/intent_schema.md`).
- Example fixtures validate with no warnings.
- Schema export is used by prompts (no manual duplication of field names/types).

### What to test (QA)
- Unit: parsing valid fixtures passes; invalid fixtures fail with clear error messages.
- Negative tests: missing required fields; wrong types; extra keys; invalid `YYYY-MM`.
- Consistency: schema version is enforced.

---

## M14-02 — Interpreter LLM step: prompt + runtime + deterministic fallbacks
- **Status:** NOT STARTED
- **Owner (Dev):** LLM Dev
- **QA:** QA Engineer

### Description
Implement the Interpreter LLM call that converts free text → ScenarioIntent **only**. Add robust parsing, retries, and fallback behavior so it never crashes the UI.

### Deliverables
- `llm/prompts/intent_interpreter.md` (single prompt, versioned header)
- `llm/intent_interpreter.py` (LLM call, parse, retry, fallback)
- `demo/llm_intent_check.py` CLI
- `tests/test_intent_interpreter_parsing.py` (parser + retry behavior with mocked LLM)

### Runtime requirements
- If the model returns non-JSON or JSON with code fences: strip + parse.
- If still invalid: retry with a “repair” prompt once; then return:
  - `need_clarification=true` and a generic clarifying question (not an exception).

### Definition of Done
- For the sample prompt set (≥ 25), Interpreter returns valid ScenarioIntent for ≥ 90% without retries; remaining cases yield clarification.
- No stack traces leak to Streamlit; errors are surfaced as user-friendly messages.
- Interpreter includes **explicit unit guidance** (percent = decimals) but does **not** output params.

### What to test (QA)
- Mocked LLM returns:
  - valid JSON → parse OK
  - JSON wrapped in ```json fences → parse OK
  - partial JSON → repair retry triggers and then returns clarification
- Integration smoke (manual):
  - “hiring freeze from 2028” → `intent_type=policy`, `timing.start=2028-01`, `driver=cost` or `auto`
  - “simulate US invasion in 2029” → `intent_type=shock`, `severity=crisis`, `timing.start=2029-01` (or close)

---

## M14-03 — Compiler: templates-first mapping ScenarioIntent → ScenarioParamsV3
- **Status:** NOT STARTED
- **Owner (Dev):** Backend Dev
- **QA:** QA Engineer

### Description
Implement a Compiler that produces full ScenarioParamsV3 deterministically using templates per intent_type, with LLM fallback only if required.

### Deliverables
- `scenarios/compiler_v3.py`
- `scenarios/templates/`:
  - `policy.py`, `shock.py`, `target.py`, `constraint.py`, `mix_shift.py`, `productivity.py`, `attrition.py`, `relocation.py`
- `docs/compiler_rules.md` (mapping tables + defaults)
- `tests/test_compiler_templates.py` (unit tests for each template)

### Template defaults (must be explicit and documented)
- Default `ramp_months`: 3 (policy), 6 (target), 1 (shock)
- Default `duration_months`: None (permanent) unless intent implies temporary
- Default `severity` affects magnitude bands:
  - operational: mild (e.g., level change <= 10%, growth delta <= 2pp YoY)
  - stress: moderate
  - crisis: higher but bounded

### Definition of Done
- For every valid ScenarioIntent, compiler returns a fully populated ScenarioParamsV3 (no missing required fields).
- If intent is ambiguous, compiler returns a safe default **and** sets `need_clarification=true` with exactly one question.
- Compiler emits a structured `CompileResult` containing:
  - `params_v3`
  - `human_summary` (1–2 sentences)
  - `assumptions` (bullets)
  - `needs_clarification` + question

### What to test (QA)
- Unit: each template covers expected intents and respects timing.
- Regression: “keep costs flat” compiles to driver `cost` with growth constraints (not nonsense FTE collapse without warning).
- Edge: if `timing.start` beyond horizon → compiler sets clarification (not crash).

---

## M14-04 — Normalize units before validation (percent-as-whole-number)
- **Status:** NOT STARTED
- **Owner (Dev):** Backend Dev
- **QA:** QA Engineer

### Description
Add normalization for percent-like fields (e.g., 5 → 0.05) before validation/apply. Prevent spam by producing one concise warning summary.

### Deliverables
- `scenarios/normalize_params.py`
- integrated into the pipeline: **Interpreter → Compiler → Normalize → Validate → Apply**
- `tests/test_normalize_params.py`

### Normalization rules
- For fields representing percentages/pp (document exact list):
  - if `abs(x) > 1.5`, set `x = x/100`
  - add a warning: `Normalized <field>: <old> → <new> (assumed percent input)`
- Apply at most once per field.
- Deduplicate warnings (same field only once).

### Definition of Done
- Any LLM output using whole-number percent does not explode scenarios; it normalizes and proceeds.
- Warnings displayed are concise (no repeated clamp spam).

### What to test (QA)
- Unit: `5` becomes `0.05`, `-10` becomes `-0.10`, `0.08` stays `0.08`.
- Integration: prompt that previously caused clamp spam now produces single normalization note.

---

## M14-05 — Fail-open validator: block only on mathematical invalidity
- **Status:** NOT STARTED
- **Owner (Dev):** Backend Dev
- **QA:** QA Engineer

### Description
Adjust validation so typical prompts never block. Only block if applying would yield mathematically invalid outputs.

### Deliverables
- `scenarios/validate_v3.py` updated + `ValidationResult` with:
  - `errors[]` (block apply)
  - `warnings[]` (allow apply)
  - `clamps[]` (allow apply; included in warning summary)
- `tests/test_validator_fail_open.py`

### Blocking errors (only)
- NaN/inf
- negative cost/FTE after normalization/clamp
- alpha > cost after normalization/clamp (variable negative)
- impossible timing (start after horizon; negative durations)

### Warning behavior (examples)
- “Implied FTE reduction is extreme (Year-10 vs baseline < 0.5×). Proceeding anyway.”
- “CAGR exceeds normal bounds; treated as stress/crisis scenario.”
- “Monthly change exceeded cap; smoothed ramp.”

### Definition of Done
- The prompt “keep costs at current levels, what would happen to FTEs?” produces an answer:
  - apply scenario + warnings, not error.
- “US invasion 2029” yields visible change (not tiny) and does not get clamped into irrelevance unless truly out of bounds.

### What to test (QA)
- Unit: invalid inputs block; borderline inputs warn.
- Integration: previously blocked prompts now apply.

---

## M14-06 — Severity tiers wired end-to-end (Interpreter → Compiler → Validator)
- **Status:** NOT STARTED
- **Owner (Dev):** Backend/LLM
- **QA:** QA Engineer

### Description
Make severity influence magnitude defaults and validator thresholds without introducing extra UI complexity.

### Deliverables
- Severity inference rules in `intent_interpreter` prompt (examples included)
- `config/validation_caps.py` with per-severity caps
- tests verifying the tier routing

### Definition of Done
- Crisis scenarios allow stronger shocks/growth deltas while still bounded by a final hard stop (e.g., >5× baseline requires explicit “extreme” intent).
- Operational scenarios remain mild.

### What to test (QA)
- “war/invasion/sanctions” → severity crisis
- “hiring freeze” → operational
- Validator uses correct cap set based on severity.

---

## M14-07 — Streamlit integration: new “Two-step AI Scenario Assistant” panel
- **Status:** NOT STARTED
- **Owner (Dev):** App Dev
- **QA:** QA Engineer

### Description
Add a new assistant panel that:
- shows the Interpreter output (intent summary)
- shows compiled params (editable)
- validates (fail-open) and shows concise warning banner
- applies to graph deterministically

### Deliverables
- `ui/ai_assistant_two_step.py` (or refactor into `app.py` with clean boundaries)
- Updated “Apply suggestion” logic to use `CompileResult.params_v3` (not slider mutation hacks)
- `demo/smoke_ai_assistant.py` (headless-ish flow using fixtures)

### UX requirements (must)
- Always show a human summary + assumptions.
- If clarification needed: show 1 question and a button “Apply safe default anyway”.
- Warnings displayed as a short bullet list (max 5), with “show details” expander.

### Definition of Done
- No crashes when LLM returns malformed output.
- Apply button updates the plot every time (or explains why not, in-app).
- Existing V2/V3 preset workflow remains intact.

### What to test (QA)
- Manual script:
  1) enter prompt; see intent summary
  2) click compile; see params
  3) click apply; chart changes
- Automated: mock Interpreter/Compiler outputs and confirm apply updates series.

---

## M14-08 — Acceptance suite for “always answers” using real sample prompts
- **Status:** NOT STARTED
- **Owner (Dev):** QA Lead
- **QA:** QA Engineer

### Description
Add an acceptance suite that runs the pipeline on a curated set of prompts and asserts *behavioral* correctness.

### Deliverables
- `tests/fixtures/sample_prompts.json` (≥ 25 prompts, from your list + edge cases)
- `tests/acceptance/test_two_step_pipeline.py`
- `tests/acceptance/README.md` describing how to run locally

### Acceptance assertions (per prompt)
- returns either:
  - `applied=True`, or
  - `need_clarification=True` with exactly one question
- never raises unhandled exceptions
- output series finite and non-negative
- if intent_type is `shock|target|policy`, deviation vs baseline is non-trivial:
  - at least one point differs by ≥ 2% from baseline after start month
- warning count is bounded (e.g., ≤ 5 in summary)

### Definition of Done
- Acceptance suite passes in CI (or documented local runner).
- Prevents regressions that reintroduce blocking failures.

---

## M14-09 — Documentation + playbook for tuning caps safely
- **Status:** NOT STARTED
- **Owner (Dev):** Dev Lead
- **QA:** QA Lead

### Description
Document how the two-step assistant works and how to tune thresholds without breaking behavior.

### Deliverables
- `docs/ai_assistant_two_step.md`:
  - architecture diagram
  - schema versions
  - default template mapping table
  - normalization rules
  - severity tiers + thresholds
  - troubleshooting section (common failure modes + fixes)

### Definition of Done
- Another engineer can adjust caps and templates without reading prompt code.
- Docs include a “How to add a new scenario intent” section.

### What to test (QA)
- Documentation walk-through: follow docs to run CLI checks + acceptance tests.

---

## Change Log (roadmap-impacting updates)
- Introduce two-step LLM pipeline (Interpreter → Compiler) to guarantee an answer and reduce distortion.
- Convert guardrails to fail-open; block only for mathematical invalidity.
- Add unit normalization to prevent percent unit mistakes.
