# Demo Roadmap — SAC Data → Forecast (10y) → Scenarios + Narrative (+ MCP Baseline)

## 0) Goal
Deliver a **minimal, reliable demo** that:
- Pulls time-series data from **SAP Analytics Cloud (SAC)** (Data Export Service)
- Produces a **10-year forecast** + **3–5 parameterized scenarios**
- Shows results in an **external UI** (not in SAC)
- Adds an optional **AI narrative** (deterministic fallback)

Success = one-click refresh from SAC → updated charts + scenario comparison + short narrative.

---

## 1) Scope (Demo MVP)
### In scope
- **Data ingestion (SAC → demo)** via SAC Data Export Service (OData)
- **Dataset binding** (one chosen provider + one stable “slice” filter)
- **Caching** to avoid repeated pulls (local SQLite/Parquet)
- **Forecast engine** (deterministic baseline + fallback)
- **Scenario overlays** (simple param model; fast and controllable)
- **UI** (Streamlit) + optional **MCP server** for easy querying/tooling
- **Packaging**: runnable locally + docker option
- **Demo script** + minimal README

### Out of scope (explicitly)
- Writing results back to SAC (imports)
- Full enterprise auth/SSO beyond OAuth client creds
- Multi-model joins/heavy feature engineering
- Unrestricted “agent that explores SAC freely” (tool allow-list only)

---

## 2) Architecture (Thin-Slice + MCP option)
### Baseline (demo runtime)
```
SAC (Model/Provider)
  └─ Data Export Service (pull)
       └─ Demo Backend (Python)
            ├─ Ingest + normalize (time series)
            ├─ Cache (SQLite/Parquet)
            ├─ Forecast (baseline)
            ├─ Scenarios (overlay)
            ├─ Narrative (LLM + fallback)
            └─ Streamlit UI
```

### Optional (recommended) MCP layer
```
LLM / Tooling / Future Agent
  └─ MCP Server (allow-listed tools)
       └─ Same backend modules (auth/export/cache)
```

---

## 3) Confirmed Tenant Coordinates (known-good)
These are validated in the tenant with OAuth client credentials.

- Tenant URL: `https://ndcgroup.eu10.hcs.cloud.sap`
- Token URL: `https://ndcgroup.authentication.eu10.hana.ondemand.com/oauth/token`
- NamespaceID: `sac`
- ProviderName: `NICOLAS COPY_PLAN_HR_HC_PLANNING`
- ProviderID: `C6a0bs069fpsb2as72454aoh2v`
- FactData endpoint:
  - `GET /api/v1/dataexport/providers/sac/C6a0bs069fpsb2as72454aoh2v/FactData`

Required headers for DES calls:
- `Authorization: Bearer <token>`
- `x-sap-sac-custom-auth: true`

FactData schema observed (dims + measures):
- Dims: `Version, Date, GLaccount, Function, Level, DataSource, Status, EmployeeType, CostCenters, Positions`
- Measures: `SignedData, Budget, Cost, Percentage, Tech_Group_Currency`

**Demo slice strategy (to keep data small/stable):**
- Start with a single measure series (e.g., `SignedData`) and filter to a stable slice such as:
  - `Version = public.Actual`
  - `GLaccount = FTE`
  - `DataSource = Basis`
  - and fix other dims to `#` where applicable
- Then aggregate by month on `Date` (values look like `YYYYMM`).

---

## 4) Data Contract (strict)
### Required fields
- `date` (ISO; derived from SAC `Date`)
- `value` (float)

### Optional fields (keep minimal)
- up to 2 dims as `dim_*` only if needed for slicing/debugging

---

## 5) Milestones & Deliverables
### M0 — Setup & Access (DONE)
- OAuth client credentials validated
- DES reachable
- Provider identified for demo model

### M1 — Dataset Binding + MCP Baseline (NEXT)
- A single, stable **time-series query** defined (filters + select + orderby)
- `refresh()` pulls that series → normalized dataframe → cache
- **MCP server** exposes minimal tools to query the dataset

Deliverables:
- `python -m demo.refresh --source sac` writes cached normalized dataset
- `python -m demo.query` prints a quick summary (min/max date, row count)
- `python -m mcp_server` (or equivalent) runs and offers at least `get_timeseries` tool

### M2 — Baseline Forecast (10y)
- Deterministic baseline with fallback logic
- Forecast outputs saved + unit test using fixture

### M3 — Scenarios (3–5 presets)
- Base / Downside / Upside (+ optional trade-war shock, aging drift)

### M4 — UI + Narrative
- Streamlit app with refresh + charts + narrative
- LLM optional; deterministic narrative fallback

---

## 6) Guardrails (demo stability)
- If SAC pull fails → use last cached data + warning banner
- If series is empty → fail with actionable message (“check filters / version / members”)
- If forecast fails → fallback to damped CAGR
- If LLM fails → template narrative fallback
- Never log secrets/tokens

---

## 7) Definition of Done (project-level)
- One command runs end-to-end using real SAC data (or cached)
- Forecast horizon = 10 years from last observed period
- ≥ 3 scenarios with controllable parameters
- UI loads in <5 seconds (from cache)
- No hard failures if SAC/LLM unavailable (graceful fallback)
- README includes setup + run steps

---

## 8) Risks & Mitigations (updated)
- **Planning-model dimensionality** → lock a minimal filter slice; aggregate by month
- **Duplicate-looking facts** → always aggregate by `Date` after filtering (sum/mean as chosen and documented)
- **Data volume** → use `$select`, `$filter`, `$orderby`, bounded paging; cache locally
- **Narrative hallucinations** → restrict prompt to summary stats + scenario params; include assumptions
