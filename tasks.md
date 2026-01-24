# Tasks — Auto-detect Scenario Driver in AI Scenario Assistant (V3)

## Goal
Remove the “Scenario driver” dropdown from the main UI. The assistant should infer the correct driver automatically from the user text and the current model context (cost/FTE driver model, fixed vs variable cost split), then produce a safe V3 suggestion that can be applied to charts.

**Success criteria**
- User types scenario text and clicks **Get suggestion (V3)** → app returns:
  - inferred driver (Cost / FTE / Cost target)
  - parameters (V3 schema)
  - short rationale (human-readable)
  - impact preview + safety warnings (if any)
- User can click **Apply suggestion** and the graph updates correctly.
- No manual driver selection needed in the default flow.
- The output is validated and bounded (no “100x costs in 10y” suggestions).

---

## M12-01 — UI: Remove driver dropdown from default flow
**Problem**
The dropdown (“cost / fte / cost_target”) creates friction and uncertainty; users expect the assistant to decide.

**Implementation**
- Remove the driver selector from the main “AI scenario assistant (V3)” section.
- Keep an **Advanced options** expander with:
  - “Override driver (optional)” dropdown (default: auto)
  - “Show debug payload” toggle

**Acceptance**
- Default flow has no driver input.
- Advanced override works for testing.

---

## M12-02 — Prompt + schema: Make driver inference an explicit output
**Problem**
LLM currently relies on user selection; we need deterministic driver inference.

**Implementation**
- Update the V3 LLM prompt to:
  - include business assumptions (baseline growth 6%/yr, inflation drift 3%/yr, fixed cost share 20% at t0, ~800 FTE at t0, alpha/beta relationship)
  - instruct the model to **infer driver** from text:
    - “reduce costs by X%” / “hit cost target” → `cost_target`
    - “cut FTE” / “hiring freeze” / “outsource N FTE” → `fte`
    - “inflation / wage increase / contractor conversion / benefit changes” → `cost`
  - require *compact* rationale (2–5 bullets) + confidence (low/med/high)
- Extend/confirm the LLM response schema to include:
  - `driver`: one of `cost|fte|cost_target`
  - `params`: ScenarioParamsV3 (existing)
  - `rationale`: {summary, drivers[], assumptions[], confidence}
  - `safety`: {flags[], clamped_fields[], notes}

**Acceptance**
- LLM returns driver consistently for the five demo presets + free text.
- Output is strict JSON (no markdown/code fences).

---

## M12-03 — Safety & validation: Clamp unrealistic outputs before apply
**Problem**
Even good prompts can output extreme values; must be robust.

**Implementation**
Add a central validator (or extend existing V3 validator) that:
- Validates types and ranges for all V3 fields.
- Enforces growth sanity:
  - cap effective annual growth (baseline + deltas) to a reasonable band (e.g. -20% .. +20% per year) unless explicitly “catastrophe” and still bounded.
- Enforces level sanity:
  - cap implied 10-year cost multiple vs baseline (e.g. <= 3x) for demos; return warning + clamp.
- Enforces timeline sanity:
  - lag/onset/recovery durations must fit horizon; adjust or reject.
- Emits a *user-visible* warning list when clamping occurs.

**Acceptance**
- LLM cannot cause runaway curves (e.g. 100x in 10 years).
- Apply pipeline never throws due to invalid suggestion; it either clamps or shows a clear error.

---

## M12-04 — Driver resolution layer: Translate inferred driver into apply-ready params
**Problem**
The apply pipeline needs deterministic behavior per driver.

**Implementation**
Create a function (single source of truth), e.g. `resolve_driver_and_params(suggestion, context)`:
- Inputs:
  - LLM suggestion (driver + params)
  - model context (alpha, beta, fixed share, baseline growth, inflation drift, t0 cost, t0 FTE)
- Behavior:
  - `driver=cost`: apply cost-side parameters directly.
  - `driver=fte`: convert FTE change into cost change using alpha/beta model:
    - variable_cost = beta * FTE
    - fixed_cost = alpha
    - total = alpha + beta*FTE
    - keep fixed constant unless scenario says otherwise
  - `driver=cost_target`: compute implied FTE delta needed to reach target cost at t0 (or specified event time), then generate the FTE path + resulting cost path.
- Output:
  - normalized ScenarioParamsV3 suitable for `apply_scenario_v3`
  - derived metrics: implied FTE delta, implied cost delta, alpha/beta used

**Acceptance**
- “Reduce cost 10%” produces a consistent implied FTE cut (and matches the driver model).
- “Outsource 120 FTE” produces moderate savings, not extreme drops.

---

## M12-05 — UI: Show inferred driver and derived metrics clearly
**Problem**
Users need to understand what the assistant decided.

**Implementation**
In the assistant result panel, display:
- **Driver chosen:** Cost / FTE / Cost target (with one-line explanation)
- **Key numbers:** event start (e.g., T+6), magnitude, duration, recovery
- **Derived:** implied FTE change (if driver=cost_target), alpha/beta used, fixed share
- **Warnings:** safety clamps / assumptions conflicts

**Acceptance**
- User can read “Driver chosen: cost_target — you asked to reduce costs by 10%.”
- Derived numbers are visible without expanding debug.

---

## M12-06 — Apply Suggestion wiring: Make “Apply suggestion” robust for V3
**Problem**
Historically “Apply suggestion” mutated Streamlit state in ways that can break (widget key errors). We need a safe V3 path.

**Implementation**
- Store the last validated suggestion in `st.session_state["v3_suggestion"]` (immutable dict).
- On **Apply suggestion**:
  - recompute scenario series using `apply_scenario_v3` (pure function)
  - set `st.session_state["active_scenario_key"]="v3_custom"` (or similar)
  - update chart data source from state, without modifying already-instantiated widget keys
- Do not mutate widget-backed keys post-instantiation; instead:
  - keep sliders (if any) in Advanced options and update via `st.session_state.update()` before creation, or use `st.form` submit pattern.

**Acceptance**
- No Streamlit API exceptions when applying.
- Applying multiple times works.

---

## M12-07 — Tests: Golden cases for driver inference + apply
Add tests for:
1) “Inflation spike mid next year” → driver=cost, lag≈6 months, permanent level step, same slope as baseline.
2) “Freeze hiring” → driver=fte, growth slows to inflation-only (≈3%) vs baseline 6%.
3) “Outsource 120 FTE from UK to CZ” → driver=fte, ramp over 6–12 months, moderate savings.
4) “Convert IT contractors to employees” → driver=cost, temporary savings + then return to baseline slope.
5) “Reduce workforce costs by 10%” → driver=cost_target, implied FTE cut consistent with alpha/beta and fixed share.

**Acceptance**
- Each test asserts:
  - driver classification
  - params validity
  - cost multiple bounds
  - expected trend behavior (no sudden collapse unless asked)

---

## Optional copy tweaks (SAP-ish)
- Rename “AI scenario assistant” → **“Scenario Copilot”**
- Replace placeholder with: “Example: ‘Inflation spike mid next year (+5%)’”
- Replace internal driver labels:
  - cost → “Costs”
  - fte → “Headcount (FTE)”
  - cost_target → “Cost target”
