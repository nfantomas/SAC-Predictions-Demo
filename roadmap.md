# Demo Roadmap — SAC Data → Forecast (10y) → Scenarios + Narrative

## 0) Goal
Deliver a **minimal, reliable demo** that:
- Pulls time-series data from **SAP Analytics Cloud (SAC)**
- Produces a **10-year forecast** + **3–5 parameterized scenarios**
- Shows results in an **external UI** (not in SAC)
- Adds an **AI-generated narrative** (optional but recommended) explaining drivers like aging, trade wars, etc.

Success = one-click refresh from SAC → updated charts + scenario comparison + short narrative.

---

## 1) Scope (Demo MVP)
### In scope
- **Data ingestion (SAC → demo)** via SAC export API (OData/REST export endpoints)
- **Caching** to avoid repeated pulls (local SQLite/Parquet)
- **Forecast engine** (deterministic baseline + fallback)
- **Scenario overlays** (simple param model; fast and controllable)
- **UI** (Streamlit) with:
  - baseline + scenarios chart
  - scenario selector & parameters
  - AI narrative panel
  - “Refresh from SAC” button
- **Packaging**: runnable locally + docker option
- **Demo script** + minimal README

### Out of scope (explicitly)
- Writing results back to SAC (imports)
- Full enterprise auth/SSO integration beyond OAuth client creds
- Large-scale data modeling, multi-model joins, heavy feature engineering
- “Autonomous agent” that explores SAC freely (guardrails-first approach)

---

## 2) Architecture (Thin-Slice)
```
SAC (Model)
  └─ Export API (pull)
       └─ Demo Backend (Python)
            ├─ Ingest + normalize
            ├─ Cache (SQLite/Parquet)
            ├─ Forecast (baseline)
            ├─ Scenarios (overlay)
            ├─ Narrative (LLM)
            └─ Streamlit UI
```

### Components
1) `sac_connector/`
- OAuth client credentials
- Data export calls (filters, time grain)
- Pagination + retry
- Output normalized to: `date, metric, dimensions(optional)`

2) `pipeline/`
- Validate schema, handle missing values
- Aggregate to chosen grain (month/quarter/year)
- Cache read/write

3) `forecast/`
- Baseline forecast (choose one):
  - Primary: Prophet/ETS/ARIMA (lightweight)
  - Fallback: CAGR + dampening
- Output: forecast series + confidence band (optional)

4) `scenarios/`
- Parameterized overlays (fast, explainable):
  - `growth_delta_pp` (± p.p.)
  - `shock_year` + `shock_pct` (one-off hit)
  - `drift_pp_per_year` (gradual change)
- Output: scenario series derived from baseline

5) `narrative/`
- Input: summary stats + scenario params (NOT raw row-level data)
- Output: short narrative + bullet “drivers” + assumptions
- Guardrails: deterministic template fallback if LLM unavailable

6) `ui/`
- Streamlit app:
  - data status (last refresh, row counts)
  - plot baseline + scenario lines
  - controls for scenario knobs
  - narrative panel + “what to ask next”

---

## 3) Data Contract (keep it strict)
### Required fields
- `date` (ISO, aligned to grain)
- `value` (float)
- Optional: 1–2 dims for slicing (e.g., region, product group)

### Demo dataset constraints (recommended)
- 1 metric, <= 2 dimensions, 5–10 years history if possible
- If history is short: switch baseline method to damped CAGR

---

## 4) Milestones & Deliverables (fast delivery)
### M0 — Setup & Access
- SAC OAuth client created + permissions validated
- One model + one query confirmed (small dataset)
**Deliverable:** connectivity checklist + working token flow

### M1 — Data Pull + Cache
- `refresh()` pulls data → normalized dataframe → cache
- Re-runs are instant from cache
**Deliverable:** CLI command `python -m demo.refresh` + cached dataset

### M2 — Baseline Forecast (10y)
- Deterministic baseline with fallback logic
- Basic validation & plots
**Deliverable:** forecast outputs saved + unit test on sample data

### M3 — Scenarios (3–5 presets)
- Base / Downside / Upside + optional “trade war shock” and “aging drift”
- Scenario parameters visible & editable in UI
**Deliverable:** scenario comparison chart + exported CSV

### M4 — UI + Narrative
- Streamlit app with refresh + charts + narrative
- LLM optional; template fallback
**Deliverable:** demo app + 2-minute scripted walkthrough

---

## 5) Implementation Plan (Work Breakdown)
### 5.1 Repo structure
- `app.py` (Streamlit entry)
- `demo/refresh.py`, `demo/run.py`
- `sac_connector/`, `pipeline/`, `forecast/`, `scenarios/`, `narrative/`
- `data/` (local cache, excluded from git)
- `tests/` (smoke + regression)

### 5.2 Minimal APIs
- `get_data(source="sac"|"cache", filters={...})`
- `run_baseline(series, horizon_years=10, method="auto")`
- `apply_scenarios(baseline, presets + user_params)`
- `generate_narrative(stats, scenario_params, market_indications_text)`

### 5.3 Guardrails (demo stability)
- If SAC pull fails → use last cached data + banner warning
- If forecast fails → fallback to damped CAGR
- If LLM fails → template narrative fallback

---

## 6) Demo Flow (what you show)
1) Open UI → “Dataset last refreshed: …”
2) Click **Refresh from SAC** → shows row count + latest date
3) Show **Baseline 10y** forecast chart
4) Toggle scenarios:
   - Downside: trade-war shock year + growth -X p.p.
   - Upside: growth +Y p.p.
   - Aging drift: gradual -Z p.p./year
5) Open **Narrative** panel:
   - “What changed?” “Why scenarios differ?” “Key assumptions”
6) Close with: “We can calibrate drivers with customer inputs & add more dims.”

---

## 7) Acceptance Criteria (Definition of Done)
- One command runs end-to-end using real SAC data (or cached)
- Forecast horizon = 10 years from last observed period
- At least 3 scenarios with controllable parameters
- UI loads in <5 seconds (from cache)
- No hard failures if SAC/LLM unavailable (graceful fallback)
- README includes setup + run steps

---

## 8) Dependencies / Prereqs
- SAC tenant access + OAuth client credentials
- Selected model/query with stable dimensions & grain
- Python 3.11+, optional Docker
- If using LLM: API key + network access (optional)

---

## 9) Risks & Mitigations
- **SAC export complexity / permissions** → validate M0 with smallest dataset first
- **Data volume / performance** → aggregate at source, cache locally
- **Short history** → use damped CAGR + wider uncertainty messaging
- **Narrative hallucinations** → constrain prompts to scenario params + summary stats; include “assumptions” section

---

## 10) Next-step Enhancements (post-demo backlog)
- Write-back to SAC planning model (round-trip)
- Multi-metric / multi-dim forecasting
- Automated driver calibration (fit shocks/drifts to known events)
- Agentic MCP layer with tool-based access & strict allow-list
