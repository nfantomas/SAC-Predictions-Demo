# tasks.md — Demo Delivery Tasks (Developer Assignment Source of Truth)

## Workflow (rules)
- **Developers only take tasks listed here.** New work = new task in this file.
- Each task has: **Owner (Dev)** → **PR** → **QA (review + tests)** → **Done**.
- QA verifies unit + integration/smoke checks and the **Definition of done**.
- **Milestone gating:** Only when all tasks in a milestone are **DONE** do we start the next milestone by adding the next milestone section.
- **Roadblocks:** If blocked by missing constraints or SAC limitations, update **roadmap.md** and record it in **Change Log**.

---

## Status legend
- `NOT STARTED`
- `IN PROGRESS`
- `IN QA`
- `BLOCKED`
- `DONE`

---

## Milestone M0 — Setup & Access (DONE)
Complete.

## Milestone M1 — Dataset Binding + MCP Baseline (DONE)
Complete.

## Milestone M2 — Baseline Forecast (10y) (DONE/IN QA)
(Complete once QA signs off.)

---

## Milestone M3 — Scenarios (3–5 presets) (NEXT)
**Milestone goal:** generate 3–5 explainable scenario series derived from the baseline forecast and persist them as artifacts for UI/MCP use.

### Scenario model (must be implemented as documented)
Scenarios are **overlays on the baseline forecast** (`yhat`), not re-fitting models.

Parameters (all optional; defaults = 0 / None):
- `growth_delta_pp`: float (percentage points). Adds a constant delta to monthly growth rate.
- `shock_year`: int (e.g., 2027) or None.
- `shock_pct`: float (e.g., -0.08 for -8%). Applied as a **level multiplier** to all months in `shock_year` and onward (i.e., permanent step change from that year).
- `drift_pp_per_year`: float. Adds a linear drift to growth over time (converted to monthly drift = drift_pp_per_year / 12).

Rules:
- Scenario series starts at the **first forecast month** (month after last actual) and spans the same horizon as baseline.
- Non-negativity: final scenario values are clipped at 0.0 (documented).
- Deterministic: no randomness.

Presets (minimum required):
- `base`: all params = 0/None
- `downside_trade_war`: shock + negative growth delta (values to be finalized and documented)
- `upside`: positive growth delta (values to be finalized and documented)
Optional (if quick):
- `aging_drift`: negative drift_pp_per_year
- `recovery`: short-term shock then partial rebound (only if explicitly implemented; otherwise omit)

---

### M3 Task List

#### M3-01 — Implement scenario overlay engine
- **Status:** DONE
- **Owner (Dev):** Data/ML Dev (Python)
- **QA:** QA Engineer
- **Description:** Implement the scenario overlay math that converts a baseline forecast series into a scenario series using the parameter model above.
- **Deliverable:** `scenarios/overlay.py` with API:
  - `apply_scenario(baseline_df, params, scenario_name) -> scenario_df`
  - `apply_presets(baseline_df, presets_dict) -> scenarios_df`
- **Definition of done:**
  - Inputs:
    - `baseline_df` contains columns `date` (ISO) and `yhat` (float) for **forecast horizon only**.
  - Outputs:
    - `scenario_df` contains `date`, `scenario`, `yhat`
    - `scenarios_df` contains concatenated results for multiple scenarios
  - Overlay behavior matches the documented rules:
    - growth_delta_pp adjusts monthly growth consistently
    - shock_year applies a permanent level multiplier from the first month of that year onward
    - drift applies monthly linear growth adjustment
  - Values are clipped at 0.0 and the clipping is unit-tested.
- **What to test (QA):**
  - Unit tests (offline):
    - With a synthetic baseline (known growth), verify growth_delta shifts results as expected.
    - Shock behavior: dates before shock_year unchanged; dates from shock_year onward multiplied by (1 + shock_pct).
    - Drift: later months diverge more than earlier months with correct sign.
    - Non-negativity clipping works for extreme negative shocks.
    - Determinism: repeated calls produce identical outputs.

---

#### M3-02 — Define scenario presets (3 required, up to 5) and document them
- **Status:** DONE
- **Owner (Dev):** Product/Backend Dev
- **QA:** QA Lead
- **Description:** Create a small set of scenario presets with customer-friendly names and fixed parameter values. Keep them explainable.
- **Deliverable:**
  - `scenarios/presets.py` (or `scenarios/presets.yaml` if preferred) defining:
    - `base`, `downside_trade_war`, `upside` (+ optional `aging_drift`, `recovery`)
  - `docs/scenarios.md` describing each preset and its parameter values
- **Definition of done:**
  - At least 3 presets exist and are used by code.
  - Each preset has:
    - name, short description, parameter dict, and intended “story” (1–2 lines)
  - `docs/scenarios.md` includes a table with exact parameter values and the rule interpretation (shock permanence, drift meaning).
- **What to test (QA):**
  - Documentation review: presets in docs match presets in code exactly.
  - Unit: loading presets returns required keys and correct types (floats/ints/None).

---

#### M3-03 — Add scenario runner + artifacts (save to cache with metadata)
- **Status:** DONE
- **Owner (Dev):** Backend Dev (Integration)
- **QA:** QA Engineer
- **Description:** Load baseline forecast artifacts, generate scenario series for presets, and write scenario artifacts to cache for UI/MCP.
- **Deliverable:**
  - `pipeline/scenario_runner.py` that:
    - loads `data/cache/forecast.*`
    - applies presets
    - writes `data/cache/scenarios.parquet` (or `.csv`) + `data/cache/scenarios_meta.json`
  - `demo/scenarios.py` runnable: `python -m demo.scenarios`
- **Definition of done:**
  - `python -m demo.scenarios`:
    - exits 0 on success
    - prints: number of scenarios, rows per scenario, min/max date
  - If forecast artifacts missing/corrupt:
    - exits non-zero with actionable message: “Run `python -m demo.forecast` first.”
  - Metadata includes:
    - `generated_at`, `presets` (names + params), `horizon_months`, `output_min_date`, `output_max_date`
- **What to test (QA):**
  - Integration (offline using fixture cache + forecast):
    - run forecast → run scenarios → artifacts created and readable
  - Negative:
    - delete forecast artifacts → scenarios command fails with actionable message
  - Idempotency:
    - rerun scenarios twice → same row counts and dates

---

#### M3-04 — Extend MCP server to expose baseline forecast + scenarios (read-only from cache)
- **Status:** DONE
- **Owner (Dev):** Backend Dev (Platform)
- **QA:** QA Lead
- **Description:** Add allow-listed tools that serve cached forecast and scenario outputs so UI/clients can query without re-running computations.
- **Deliverable:** MCP server updates adding tools:
  - `get_forecast(from_cache: bool=True)` → returns baseline forecast series
  - `get_scenarios(from_cache: bool=True, scenario: str|None=None)` → returns all scenarios or one scenario
- **Definition of done:**
  - Server lists new tools and they return quickly from cache.
  - Default is cache-only; refreshing (if supported) requires explicit flag and uses existing runners.
  - Inputs are validated:
    - unknown scenario name → clear error listing valid scenario names
- **What to test (QA):**
  - Integration:
    - generate forecast + scenarios → start MCP server
    - call `get_forecast(from_cache=True)` → returns rows
    - call `get_scenarios(from_cache=True, scenario="base")` → returns rows only for base
    - call with invalid scenario → returns error + valid scenario list

---

#### M3-05 — Add a scenario comparison smoke path
- **Status:** DONE
- **Owner (Dev):** QA Engineer (Automation) or Backend Dev
- **QA:** QA Lead
- **Description:** Add a quick smoke command that verifies the end-to-end chain up to scenarios using fixture mode.
- **Deliverable:** `demo/smoke_scenarios.py` runnable as `python -m demo.smoke_scenarios`
- **Definition of done:**
  - Command runs:
    1) refresh (fixture) → forecast → scenarios
    2) prints `SCENARIOS SMOKE OK`
  - Verifies:
    - at least 3 scenarios exist
    - scenario output dates match baseline forecast dates exactly
- **What to test (QA):**
  - Offline on clean checkout:
    - `pytest -q`
    - `python -m demo.smoke_scenarios` prints `SCENARIOS SMOKE OK`

---

## Milestone Exit Criteria (M3)
- ≥ 3 scenario series generated from baseline forecast
- Scenario artifacts written to cache and readable
- MCP exposes forecast + scenarios (read-only by default)
- Smoke path validates refresh → forecast → scenarios (fixture mode)
- All M3 tasks are `DONE` with QA sign-off

---

## Change Log (roadmap-impacting updates only)
- 2025-12-24: Added M3 scenario milestone tasks (overlay model + presets + artifacts + MCP read tools).
