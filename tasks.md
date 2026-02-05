# tasks.md — M13 Validator + Prompt Improvements (Driver Model V3)

## Goal
Stop the app from failing on realistic executive questions (e.g., “keep costs flat, what happens to FTEs?”), while still preventing absurd outputs (e.g., 100× cost increase in 10 years). Improve prompt grounding so macro/geopolitical prompts translate into visible, explainable impacts using the existing V3 methodology.

## Non-goals
- No new data sources.
- No full rebuild of scenario engine; extend existing V3 apply + validation + prompt wiring.
- Do not remove existing hard safety protections for NaNs/negatives/unbounded queries.

## Guardrails
- Preserve backwards compatibility: existing V2 flow and existing V3 presets must keep working.
- Validation must never crash the app: return structured validation results (errors/warnings) and display them.
- Hard errors only for mathematically invalid states; “unrealistic but possible” becomes warning + explanation.

---

## M13-01 Introduce ValidationResult with severity (NO MORE raising)
**Owner:** Backend  
**Type:** Refactor + Safety  

**Description:** Replace “raise Exception” style validation failures with a structured object:
- `errors: list[ValidationIssue]`
- `warnings: list[ValidationIssue]`
- `clamps: list[ClampEvent]` (optional)

**Acceptance criteria**
- No validation path throws uncaught exceptions in the Streamlit UI.
- UI shows errors/warnings in a compact banner/panel.
- Errors block “Apply suggestion”; warnings allow apply with a visible warning.

**DoD**
- Unit tests: validator returns results for failing cases instead of raising.

---

## M13-02 Split validation into Hard Errors vs Soft Warnings
**Owner:** Backend  
**Type:** Logic change  

**Description:** Implement clear categories.

### Hard errors (block apply)
- Any NaN/inf in produced series.
- Any negative costs or negative FTE after clamping (cost >= 0, FTE >= 0).
- `alpha > cost` at any month (implied variable cost negative) after clamping and/or tolerance.
- Out-of-range requested dates (index out of series) / inconsistent params.
- Month-over-month jumps beyond stability cap **only if** not explicitly requested (see M13-04).

### Soft warnings (allow apply)
- Strong deviation vs baseline (e.g., implied FTE much lower than baseline).
- “Aggressive” but within caps growth/level impacts.
- Large one-time level reset (above a warning threshold but below hard cap).

**Acceptance criteria**
- Scenario “keep costs at current levels, what happens to FTEs?” produces warnings at most, no hard error.
- Existing presets still apply without errors.

---

## M13-03 Replace “projection multiplier” hard bound with interpretable caps
**Owner:** Backend  
**Type:** Validator update  

**Description:** Remove/relax the current `projection multiplier 0.xx out of bounds` error. Replace with:

1) **Cost CAGR cap (hard)** over horizon:
- Default allowed `cost_cagr_min = -20%/yr`, `cost_cagr_max = +30%/yr`.

2) **FTE CAGR cap (hard)** over horizon:
- Default allowed `fte_cagr_min = -25%/yr`, `fte_cagr_max = +25%/yr`.

3) **Baseline-relative deviation (warning)**:
- If `scenario_cost_y10 / baseline_cost_y10 < 0.5` or `> 2.0` → warning.
- If `scenario_fte_y10 / baseline_fte_y10 < 0.5` or `> 2.0` → warning.

(Thresholds configurable.)

**Acceptance criteria**
- A “flat cost” scenario no longer fails just because it deviates from baseline.
- Absurd “100× in 10 years” is blocked by CAGR cap.

---

## M13-04 Stability cap: keep MoM clamp, but make it intent-aware
**Owner:** Backend  
**Type:** Safety enhancement  

**Description:** Keep the existing per-month clamp (e.g., ±50% MoM), but change handling:
- If scenario explicitly asks for a shock (keywords detected OR LLM sets `impact_mode=level` with magnitude above a threshold), allow higher short-term MoM movement **up to a configurable shock cap** (e.g., ±80%).
- Record clamp events in `clamps` and show them in UI as a warning (“We clamped extreme monthly changes for stability.”)

**Acceptance criteria**
- Shock prompts do not get silently flattened; they still show a visible impact.
- Clamp is visible and explainable.

---

## M13-05 Prompt update: ground in driver model + expected magnitudes
**Owner:** LLM/Prompting  
**Type:** Prompt + schema change  

**Description:** Update the V3 master prompt to include:
- Driver model: `Cost = alpha + beta * FTE`, with demo defaults (alpha=20% of t0 cost).
- Baseline assumptions: baseline cost growth ~6%/yr; inflation drift ~3%/yr.
- A “translation table” from user language → V3 levers:
  - “keep costs flat” → cost driver, set long-term growth to 0%/yr (or inflation-only if specified).
  - “reduce costs by X%” → cost_target driver, compute implied FTE cut.
  - “cut FTE by X%” → fte driver (cost changes via beta*FTE).
  - macro/geopolitical shock → level reset + temporary growth delta + optional recovery.

Also include **safety instructions**: avoid outputs that imply >2× or <0.5× baseline at Year-10 unless user explicitly requests “extreme”.

**Acceptance criteria**
- For “keep costs at current levels, what would happen to FTEs?” LLM chooses the correct driver automatically and emits consistent params.
- For “simulate US invasion in 2029” LLM produces a visible impact (not a tiny default), still within validator caps.

---

## M13-06 Schema update: allow `scenario_driver=auto` + add rationale
**Owner:** LLM/Backend  
**Type:** Schema + parsing  

**Description:** Extend the LLM output schema with:
- `scenario_driver`: `auto|cost|fte|cost_target`
- `driver_rationale`: short string (1 sentence) explaining selection (display in UI)

Backend behavior:
- If `auto`, backend resolves driver from intent heuristics + fields present.
- If driver is present, respect it.

**Acceptance criteria**
- UI no longer asks the user to choose a driver.
- Driver selection is displayed (e.g., “Driver: cost (you asked to keep costs flat)”).

---

## M13-07 Apply pipeline: use driver from LLM response to update the graph
**Owner:** App/UI  
**Type:** Integration  

**Description:** Update “Apply suggestion” to:
1) Parse LLM response (driver + params).
2) Run validator → get errors/warnings/clamps.
3) If errors: show errors, do not apply.
4) If warnings only: apply and show warnings.
5) Update scenario series + KPI cards + (if available) implied FTE and seniority table.

**Acceptance criteria**
- Driver coming from LLM response changes what is applied (cost vs fte vs cost_target).
- No app crash on validation issues.

---

## M13-08 Add regression tests for the two failing client prompts
**Owner:** Backend  
**Type:** Tests  

**Description:** Add tests (golden expectations) for:

1) **Flat cost implies FTE**
Prompt: “keep costs at current levels, what would happen to FTEs?”
Expected:
- driver = cost (or auto→cost)
- no hard errors
- scenario cost stays near t0 (within tolerance)
- implied FTE non-negative and stable-ish (or declines vs baseline if baseline grows)

2) **Macro shock is visible**
Prompt: “We are a European company, simulate US invasion in 2029”
Expected:
- non-trivial impact vs baseline (level reset and/or temporary growth delta)
- passes hard caps (CAGR etc.)
- warnings allowed, no hard errors

**Acceptance criteria**
- Tests pass and prevent regression to “0.19× out of bounds” failures.

---

## M13-09 UI: executive-friendly explanation of warnings and clamps
**Owner:** App/UI  
**Type:** UX  

**Description:** Add a compact component under the assistant:
- “What changed” bullets (derived from driver + params + rationale)
- Warnings banner with short language (no stack traces)
- Optional “Details” expander with clamp events + thresholds

**Acceptance criteria**
- User understands why FTE changes when costs are held flat.
- Warnings are readable and actionable.

---

## M13-10 Centralize thresholds into config
**Owner:** Backend  
**Type:** Maintainability  

**Description:** Move caps/thresholds into a single config file/module (e.g., `config.py` or `validation_caps.yaml`):
- cost_cagr_min/max
- fte_cagr_min/max
- baseline_relative_warn_thresholds
- mom_stability_cap
- shock_mom_cap
- alpha_cost_share_default (20%)

**Acceptance criteria**
- Threshold changes require updating one place only.
- Defaults match demo assumptions.

---

## Suggested demo defaults (for reference)
- Baseline cost growth: **6%/yr**
- Inflation drift: **3%/yr**
- Fixed cost share at t0: **20%** (`alpha = 0.2 * t0_cost`)
- Variable per-FTE cost: `beta = (t0_cost - alpha) / t0_fte`
- Hard caps (defaults):
  - Cost CAGR: **[-20%, +30%]**
  - FTE CAGR: **[-25%, +25%]**
  - MoM stability cap: **±50%**, shock cap **±80%** (intent-aware)
- Baseline-relative warnings:
  - Warn if Year-10 ratio vs baseline `<0.5` or `>2.0`
