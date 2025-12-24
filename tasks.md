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

---

## Milestone M1 — Dataset Binding + MCP Baseline (DONE)
Complete.

Confirmed demo provider coordinates:
- NamespaceID: `sac`
- ProviderID: `C6a0bs069fpsb2as72454aoh2v`
- ProviderName: `NICOLAS COPY_PLAN_HR_HC_PLANNING`

Locked demo series (agreed target):
- Metric: `SignedData`
- Slice: `Version=public.Actual`, `GLaccount=FTE`, `DataSource=Basis`, other dims = `#`
- Aggregation: **SUM by month**
- Grain: monthly (`Date` in `YYYYMM`)

---

## Milestone M2 — Baseline Forecast (10y) (CURRENT)
**Milestone goal:** produce a deterministic 10-year baseline forecast from the cached normalized time series with robust fallbacks and clear test coverage.

### M2 Task List

#### M2-01 — Implement baseline forecaster (ETS) with fallback (damped CAGR)
- **Status:** DONE
- **Owner (Dev):** Data/ML Dev (Python)
- **QA:** QA Engineer
- **Description:** Implement baseline forecasting that prefers ETS/Exponential Smoothing on monthly data and falls back to damped CAGR when history is insufficient or model fit fails.
- **Deliverable:**
  - `forecast/baseline.py` with API:
    - `run_baseline(series_df, horizon_months=120, method="auto") -> forecast_df`
  - Forecast output schema (minimum):
    - `date` (ISO, monthly, first of month)
    - `yhat` (float)
    - optional: `yhat_lower`, `yhat_upper` (if cheap to compute; otherwise omit)
- **Definition of done:**
  - `method="auto"` selects ETS when:
    - data is monthly and has >= 24 points (or documented threshold), else uses CAGR fallback.
  - Forecast length = **120 months** (10 years) starting the month after last observed date.
  - Deterministic outputs (no randomness, stable results across runs with same input).
  - Headcount-safe default: forecast values are **not negative** (clip at 0 or enforce constraint; document behavior).
  - Clear error handling: when ETS fails, logs a single-line reason and uses fallback (no hard crash).
- **What to test (QA):**
  - Unit tests (offline):
    - Auto selection: 12 points → fallback chosen; 36 points → ETS chosen.
    - Output length and date continuity (monthly increments, correct start date).
    - Non-negativity behavior (if clipping is implemented).
    - ETS failure path triggers fallback (simulate by passing degenerate data).
  - Regression test:
    - On fixture dataset, forecast first 3 `yhat` values remain within an expected tolerance range (to catch accidental behavior changes).

---

#### M2-02 — Add forecast runner + artifacts (save to cache with metadata)
- **Status:** DONE
- **Owner (Dev):** Backend Dev (Integration)
- **QA:** QA Lead
- **Description:** Add a runnable path that loads the cached normalized series, computes the baseline forecast, and writes forecast artifacts to `data/cache/` with metadata for UI use.
- **Deliverable:**
  - `pipeline/forecast_runner.py` (or similar) that:
    - loads normalized cache (`date`, `value`)
    - calls `forecast.run_baseline(...)`
    - writes `data/cache/forecast.parquet` (or `.csv`) + `data/cache/forecast_meta.json`
  - `demo/forecast.py` runnable: `python -m demo.forecast`
- **Definition of done:**
  - `python -m demo.forecast`:
    - exits 0 on success
    - prints: input row count, min/max date, forecast horizon, and output path
  - If series cache missing/corrupt:
    - exits non-zero with actionable message: “Run `python -m demo.refresh --source sac` first.”
  - Metadata includes:
    - `generated_at`, `horizon_months`, `method_used`, `input_min_date`, `input_max_date`, `output_min_date`, `output_max_date`
- **What to test (QA):**
  - Integration (offline using fixture cache):
    - run refresh (fixture mode) → run forecast → artifacts created and readable
  - Negative:
    - delete cache → forecast command fails with actionable message
  - Idempotency:
    - rerun forecast twice → same number of rows; dates identical; no duplicate rows

---

#### M2-03 — Add `demo.run` one-command demo path (refresh → forecast) with safe fallbacks
- **Status:** DONE
- **Owner (Dev):** Backend Dev (Platform)
- **QA:** QA Engineer
- **Description:** Provide a single “happy path” entrypoint for demos that refreshes from SAC (or uses cache on failure) and then produces forecast artifacts.
- **Deliverable:** `demo/run.py` runnable as `python -m demo.run`
- **Definition of done:**
  - `python -m demo.run` performs:
    1) refresh from SAC (or cache fallback) with summary print
    2) baseline forecast generation with summary print
  - If SAC is down but cache exists:
    - run still succeeds using cached series.
  - If SAC is down and cache missing:
    - run exits non-zero with clear remediation steps.
- **What to test (QA):**
  - Integration (requires SAC):
    - with valid creds: run completes end-to-end
  - Integration (offline):
    - with fixture cache present: run completes and generates forecast
  - Failure simulation:
    - set invalid secret + existing cache → run completes using cache and prints warning

---

#### M2-04 — Document baseline forecasting assumptions + outputs
- **Status:** DONE
- **Owner (Dev):** Data/ML Dev (Python)
- **QA:** QA Lead
- **Description:** Document what the baseline forecast does, when it switches to fallback, and how to interpret outputs.
- **Deliverable:** `docs/forecast.md`
- **Definition of done:**
  - Document includes:
    - input contract (`date`, `value`) and required grain (monthly)
    - method selection rules + thresholds
    - non-negativity behavior
    - output artifact locations + schema
    - quick “verify forecast” checklist (row counts, date ranges)
- **What to test (QA):**
  - Documentation review: steps match actual CLI behavior
  - Smoke: follow doc on clean checkout and generate forecast artifacts (fixture mode)

---

## Milestone Exit Criteria (M2)
- Baseline forecast (120 months) can be generated from cached normalized series
- Fallback logic prevents hard failures and is tested
- One-command demo path exists (`python -m demo.run`)
- All M2 tasks are `DONE` with QA sign-off

---

## Change Log (roadmap-impacting updates only)
- 2025-12-24: Started M2 forecasting milestone (ETS + damped CAGR fallback) and added demo run entrypoint.
