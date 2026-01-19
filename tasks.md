# tasks.md — Next Milestone: V3 Presets + Realistic Cost Dynamics + LLM Prompt Alignment

## Status legend
- `NOT STARTED`
- `IN PROGRESS`
- `IN QA`
- `BLOCKED`
- `DONE`

---

## Milestone M10 — Make V3 scenarios realistic + align LLM with business assumptions
**Milestone goal:** Scenarios match the agreed business logic (alpha/beta + FTE), baseline grows ~3%/yr (inflation), presets are believable, and LLM suggestions follow the same assumptions with safety bounds.

### Agreed business assumptions (must be encoded in code + prompts)
- Total HR cost at **t0 ≈ 10,000,000 EUR/month**
- **Fixed share = 20%** ⇒ **alpha = 2,000,000 EUR/month**
- **FTE at t0 = 800**
- Variable pool at t0 = 8,000,000 EUR/month ⇒ **beta = 10,000 EUR/FTE/month**
- Baseline nominal HR cost trend: **~3%/yr** (inflation/wage drift) unless explicitly overridden assuming deflation (not in demo)
- Guardrails: prevent unrealistic trajectories (e.g., 100× growth in 10 years)

---

### M10-01 — Encode baseline inflation trend (~3%/yr) as the default “new normal”
- **Status:** IN QA
- **Owner (Dev):** Forecast Dev
- **QA:** QA Engineer
- **Description:** Ensure the baseline forecast (and/or cost driver model) has a default upward drift around 3% per year (configurable) so the “Base” line never trends down unless the underlying SAC actuals clearly support it.
- **Deliverable:** `config.py` (or `scenario/config.py`) with `BASELINE_INFLATION_PPY=0.03` and baseline generation logic updated accordingly.
- **Definition of done:**
  - Baseline curve increases ~3%/yr from t0 on fixture + demo dataset unless actuals indicate strong downward trend.
  - Unit test asserts baseline YoY growth is within an acceptable band (e.g., 2–4%) on the fixture.
- **What to test (QA):**
  - `pytest -q` includes a test validating default baseline slope.
  - UI: baseline line visually trends upward on fixture mode.

---

### M10-02 — Implement “alpha/beta + FTE” cost driver model (single-source-of-truth)
- **Status:** IN QA
- **Owner (Dev):** Backend Dev (Modeling)
- **QA:** QA Engineer
- **Description:** Centralize the cost identity and ensure all scenario effects route through it:
  - `cost = alpha + beta(t) * fte(t)`
  - `alpha` fixed (demo)
  - `beta(t)` grows with baseline inflation (3%/yr) and can receive permanent level resets (e.g., inflation shock)
- **Deliverable:** `model/cost_driver.py` (or similar) exposing:
  - `calibrate_alpha_beta(cost_t0, fte_t0, fixed_share)`
  - `project_beta(beta0, inflation_ppy, months, level_resets=[...])`
  - `cost_from_fte(alpha, beta_series, fte_series)`
- **Definition of done:**
  - Alpha/beta computed exactly from assumptions (10M, 800 FTE, 20% fixed).
  - Cost never falls below alpha unless explicitly allowed (should not be allowed in demo).
- **What to test (QA):**
  - Unit tests for alpha/beta calibration and beta inflation growth.
  - Cost floor test: `min(cost) >= alpha` for all presets.

---

### M10-03 — Refactor `apply_scenario_v3` to be driver-aware but **simple**
- **Status:** IN QA
- **Owner (Dev):** Backend Dev (Scenarios)
- **QA:** QA Engineer
- **Description:** Keep V3 simple and robust:
  - Support 3 impact types used in this demo:
    1) **FTE path change** (hiring freeze, layoffs, outsourcing capacity change if any)
    2) **beta level reset** (inflation shock permanent)
    3) **beta temporary reduction** (contractor conversion savings during conversion, then return to baseline growth rate with a lower level)
  - Ramps: linear ramp-in (default) + optional duration (months), no complex shapes for now.
- **Deliverable:** Updated `scenarios/v3.py` (or current V3 module) with:
  - `apply_fte_step_or_ramp(fte, delta, start_idx, ramp_months)`
  - `apply_beta_level_reset(beta, pct, start_idx)`
  - `apply_beta_temporary_delta(beta, pct, start_idx, duration_months, ramp_months)`
  - Composition: compute fte(t), beta(t) ⇒ cost(t)
- **Definition of done:**
  - No scenario produces “collapse to ~2M” unless FTE goes to ~0 (should be prevented by safety bounds).
  - Contractor conversion ends with a *parallel* trend to baseline (same growth rate), at a lower level.
- **What to test (QA):**
  - Unit tests validating expected Year-1 deltas (see presets task below).
  - Regression test comparing pre/post refactor for non-V3 parts (don’t break current refresh/baseline).

---

### M10-04 — Replace Scenario Presets with the 5 agreed “manager-friendly” presets (V3)
- **Status:** IN QA
- **Owner (Dev):** Frontend Dev (Streamlit) + Backend Dev (Scenarios)
- **QA:** QA Lead
- **Description:** Update presets and ensure they produce realistic magnitudes given alpha/beta assumptions.
- **Presets (target behaviors):**
  1) **Hiring freeze**: stop headcount growth (do not reduce current cost); keep 3%/yr inflation
  2) **Convert IT contractors → employees**: small net savings (e.g., ~2% total), ends below baseline but with same growth slope
  3) **Inflation shock (permanent)**: beta level reset (+5% to variable portion or +~4–6% total depending on fixed share) starting next year
  4) **Outsource 120 FTE UK → CZ**: moderate savings (e.g., ~4–6% total), ramp 6–12 months, optional small transition cost (optional)
  5) **Reduce workforce costs by 10%**: compute required FTE reduction given fixed share (expect >10% FTE cut). Display the implied cut.
- **Deliverable:** `scenarios/presets_v3.py` + UI preset cards updated.
- **Definition of done:**
  - Each preset includes: name, one-line business description, parameter bundle, and expected Year-1 impact range.
  - Year-1 impacts are within believable ranges (no extreme drops).
- **What to test (QA):**
  - Snapshot test: each preset produces expected sign/magnitude bands (e.g., hiring freeze ≈ near-baseline; inflation shock positive; outsourcing negative moderate; 10% target shows computed FTE cut).
  - UI: selecting each preset updates the chart and shows “Year-1 delta vs base” and “Steady-state delta”.

---

### M10-05 — Update Streamlit UI so the story is obvious (and remove “weird” lines)
- **Status:** IN QA
- **Owner (Dev):** Frontend Dev (Streamlit)
- **QA:** QA Engineer
- **Description:** Make the demo legible to senior managers:
  - Show **only**: Actuals, Baseline forecast, Selected preset forecast (and optionally one “Custom” line)
  - Add a compact “Assumptions” card (alpha/fixed share, FTE, inflation 3%)
  - Add KPI chips: `t0 cost`, `Year-1 delta`, `Year-5 delta`, `Year-10 delta`, `implied FTE change`
- **Deliverable:** `app.py` updates to chart series selection + KPI cards.
- **Definition of done:**
  - No redundant “Override” line if not used.
  - Preset selection updates KPIs instantly and clearly.
- **What to test (QA):**
  - Manual smoke: open app → pick each preset → no confusing extra curves → KPIs make sense.

---

### M10-06 — Fix LLM prompt: embed business assumptions + map text → safe V3 parameters + rationale
- **Status:** IN QA
- **Owner (Dev):** LLM Dev
- **QA:** QA Lead
- **Description:** Update the scenario assistant prompt so suggestions are grounded:
  - Include alpha/beta/FTE + 3% baseline inflation explicitly
  - Require output schema with both **params** and **rationale** (short, executive-friendly)
  - Include bounds (max changes, no 100× cost growth)
  - Instruct model: “If user asks for a reduction target, compute implied FTE cut given fixed share.”
- **Deliverable:** `narrative/scenario_assistant_v3.py` (or current LLM module) with:
  - New system prompt + few-shot examples matching the 5 presets
  - JSON schema: `{ "params": {...}, "rationale": {...}, "safety": {...} }`
- **Definition of done:**
  - LLM outputs valid JSON **without** markdown fences.
  - Rationale explains *why* numbers make sense (1–3 bullets) and references assumptions.
- **What to test (QA):**
  - `python -m demo.llm_scenario_check` succeeds and prints parsed structure.
  - Add a deterministic “mock LLM” test ensuring parser rejects markdown-fenced JSON.

---

### M10-07 — Safety validator: clamp/deny unrealistic LLM outputs before applying
- **Status:** IN QA
- **Owner (Dev):** Backend Dev (Validation)
- **QA:** QA Engineer
- **Description:** Add a validator that checks LLM-suggested params against business-safe bounds:
  - Prevent trajectories implying >X% cost change in Y months unless explicitly requested
  - Prevent beta or FTE from producing >10× cost at Year-10 in demo mode
  - Enforce cost floor alpha
  - If invalid, return a friendly message + corrected/clamped params
- **Deliverable:** `llm/validate_v3.py` with `validate_and_sanitize(params, context)->(params, warnings)`
- **Definition of done:**
  - Invalid suggestions do not crash app; user sees warning banner + sanitized values.
- **What to test (QA):**
  - Unit tests for out-of-range inputs (shock_pct, extreme growth, negative costs).
  - Integration: run scenario assistant with extreme prompt and confirm clamping + warning.

---

### M10-08 — “Apply suggestion” plumbing: LLM → validate → apply → chart (no Streamlit state errors)
- **Status:** IN QA
- **Owner (Dev):** Frontend Dev (Streamlit) + Backend Dev (LLM)
- **QA:** QA Engineer
- **Description:** Make Apply Suggestion reliable:
  - Do **not** mutate widget keys after instantiation
  - Use a dedicated `st.form` or “pending suggestion” state:
    1) Store validated suggestion in `session_state["pending_v3"]`
    2) Render a read-only summary
    3) On “Apply”, set the **scenario params object**, then `st.rerun()`
- **Deliverable:** App changes in `app.py` + helper `ui/apply_suggestion.py`
- **Definition of done:**
  - Clicking “Suggest” then “Apply” never throws `StreamlitAPIException`.
  - Chart updates to the newly applied V3 series.
- **What to test (QA):**
  - Manual: suggest → apply 10 times in a row; no errors.
  - Automated: minimal Streamlit state unit test (where feasible) or smoke script.

---

### M10-09 — Acceptance checks (demo readiness)
- **Status:** IN QA
- **Owner (Dev):** Dev Lead
- **QA:** QA Lead
- **Description:** Ensure the demo tells the right story end-to-end.
- **Deliverable:** `docs/demo_checklist.md`
- **Definition of done:**
  - Baseline grows ~3%/yr.
  - Presets produce believable magnitudes (no extreme drops/spikes).
  - LLM suggestions: grounded, rationalized, safe, and applied reliably.
- **What to test (QA):**
  - Runbook: refresh from SAC → select preset → ask LLM suggestion → apply → KPIs update.

---


## Milestone M10 — Scenario realism + LLM alignment (increment)

### M10-11 — Add explicit baseline growth assumption (6% YoY) to scenario engine defaults
- **Status:** IN QA
- **Owner (Dev):** Forecast/Scenarios Dev
- **QA:** QA Engineer
- **Description:**
  - Ensure the baseline forecast that feeds scenarios has a clear, configurable **baseline_growth_yoy** defaulting to **0.06**.
  - This should be applied consistently in the forecast generation layer (the series feeding scenario overlays), not only in UI labels.
  - Decompose baseline growth for the driver model: **fte_growth_yoy=0.03** (business growth) and **inflation_yoy=0.03** applied to cost rates (beta, and optionally alpha), yielding ~6% total cost YoY when FTE is the main driver.

  - Provide a single source of truth for this value (config + code), and expose it in UI as a read-only “Assumptions” card.
- **Deliverable:**
  - Config key (e.g., `BASELINE_GROWTH_YOY=0.06`) and applied wiring.
  - UI “Assumptions” card displays: Baseline growth 6% YoY; Inflation 3% YoY; Fixed cost share 20%; FTE 800 at t0.
- **Definition of done:**
  - Baseline forecast is upward trending at ~6% YoY (within tolerance) from t0 onward.
  - Changing config changes baseline behavior deterministically.

**What to test (QA):**
- Unit test: baseline series CAGR over first 24 months ≈ 6% YoY ± 0.5pp.
- Visual smoke: baseline line slopes upward; no negative drift unless explicitly configured.

---

### M10-12 — Redefine Hiring Freeze scenario as “inflation-only growth” (3% YoY) vs baseline (6% YoY)
- **Status:** IN QA
- **Owner (Dev):** Forecast/Scenarios Dev
- **QA:** QA Engineer
- **Description:**
  - Update the **Hiring Freeze** preset to represent: “business growth contribution removed; only inflation remains.”
  - Implementation should NOT cause steep declines or long-term collapses.
  - Mechanically:
    - Keep level at t0 unchanged.
    - During freeze: growth rate should move from baseline (~6% YoY) toward inflation-only (~3% YoY).
    - After freeze ends (if modeled as a duration): return to baseline ~6% YoY.
    - If freeze is permanent: stay at ~3% YoY.
  - Prefer a simple V3 parameterization:
    - `driver="cost"`
    - `impact_mode="growth"`
    - `event_growth_target_pp_per_year = 0.03` (inflation-only)
    - `recovery` optional (if freeze is temporary) to return to 0.06.
- **Deliverable:**
  - Updated preset definition + tests.
  - UI label: “Hiring Freeze (inflation-only growth)” with a one-line explanation.
- **Definition of done:**
  - Hiring Freeze line stays **below baseline**, but remains **upward trending** (unless user sets negative inflation).
  - Delta vs baseline grows gradually over time (no immediate cliff unless configured).

**What to test (QA):**
- Unit tests:
  - At 12 months: freeze series > t0 and < baseline.
  - CAGR of freeze series over first 24 months ≈ 3% YoY ± 0.5pp.
  - No negative values, no >2x jump year-on-year unless explicitly allowed.

---

### M10-13 — Update LLM prompt + schema guidance to respect baseline vs inflation split
- **Status:** NOT STARTED
- **Owner (Dev):** LLM/Prompt Dev
- **QA:** QA Lead
- **Description:**
  - Extend the system/prompt context used by the Scenario Assistant to include:
    - “Baseline growth assumption: 6% YoY.”
    - “Inflation component: 3% YoY.”
    - “Hiring freeze means removing business-growth contribution; only inflation remains.”
  - Add a guardrail rule: do not propose negative long-run growth for benign scenarios unless explicitly requested.
  - Ensure examples in the prompt include a hiring freeze and show the expected parameter pattern.
- **Deliverable:**
  - Updated prompt text + 2–3 few-shot examples.
  - `demo.llm_scenario_check` updated to include this context and a regression case: “hiring freeze” → growth target ~0.03.
- **Definition of done:**
  - LLM suggestions for “Hiring freeze” result in a plausible growth reduction (toward 3% YoY) rather than a level collapse.
  - Suggestions remain bounded by safety validator.

**What to test (QA):**
- Prompt regression tests:
  - Input “hiring freeze” returns growth target close to 0.03 and no shock_pct cliff.
  - Input “business expansion” keeps growth closer to 0.06 or higher but within safety bounds.

---

### M10-14 — Safety validation: clamp unrealistic long-run outcomes (e.g., 100x in 10 years)
- **Status:** NOT STARTED
- **Owner (Dev):** Backend/Validation Dev
- **QA:** QA Engineer
- **Description:**
  - Add/extend validator rules to prevent unrealistic trajectories even if the LLM proposes them:
    - Hard cap on 10-year multiplier (e.g., max 3–5x unless explicit override flag set).
    - Cap YoY growth targets (e.g., -20% to +20% for sustained growth unless “catastrophic/boom” scenario is explicitly requested).
    - Reject parameter combinations that imply negative costs.
  - On rejection, UI should show a clear message and fall back to safe defaults (or ask to rephrase).
- **Deliverable:**
  - Validator updates + unit tests.
  - UI error message for rejected suggestions.
- **Definition of done:**
  - No “100x in 10y” curves can be applied via “Apply suggestion.”

**What to test (QA):**
- Feed extreme suggestion JSON → validator rejects with actionable reason.
- Normal suggestions still pass.

---

## Notes / UX copy (keep it simple)
- Baseline label: **“Base forecast (6% YoY)”**
- Hiring Freeze label: **“Hiring freeze (3% YoY inflation-only)”**
- One-liner explanation shown under preset buttons:
  - Base: “Business + inflation growth.”
  - Hiring freeze: “No net headcount growth; costs rise with inflation only.”



## Milestone Exit Criteria (M10)
- Presets match agreed behaviors and look believable on chart.
- Baseline trend is upward by default (~3%/yr).
- LLM prompt includes the business assumptions and returns rationalized V3 suggestions.
- LLM suggestions are validated/sanitized and apply cleanly to the chart without Streamlit state errors.
