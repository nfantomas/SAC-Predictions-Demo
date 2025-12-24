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
All M0 tasks are complete and verified (OAuth client credentials + DES access + provider discovery).

Known-good demo provider:
- NamespaceID: `sac`
- ProviderID: `C6a0bs069fpsb2as72454aoh2v`
- ProviderName: `NICOLAS COPY_PLAN_HR_HC_PLANNING`

---

## Milestone M1 — Dataset Binding + MCP Baseline (CURRENT)
**Milestone goal:** reliably pull a single time series from the chosen SAC provider, cache it, and expose it via a minimal MCP server for easy querying.

### M1 Task List

#### M1-01 — Lock the “demo slice” query (select + filter + orderby) and document it
- **Status:** DONE
- **Owner (Dev):** Backend Dev (Integration)
- **QA:** QA Lead
- **Description:** Define a stable, minimal query that returns a single useful time series from the provider (avoid huge dimensional exports). Prefer `$select=Date,<measure>` + `$filter=` fixed members + `$orderby=Date asc`.
- **Deliverable:** `docs/dataset_binding.md` containing:
  - Provider coordinates (NamespaceID, ProviderID)
  - Final query string (copy/paste curl-ready)
  - Explanation of chosen measure and filter members
  - Aggregation rule (e.g., sum by Date after filtering)
- **Definition of done:**
  - Document contains one “known-good” query that returns **> 24 months** of data (or explains actual history).
  - Query uses `$select` and `$filter` (no full FactData dumps).
  - Aggregation rule is explicit and justified (sum vs avg).
- **What to test (QA):**
  - Run the curl query from `docs/dataset_binding.md` and confirm:
    - HTTP 200
    - `value` has rows
    - Dates span multiple periods
  - Spot-check that filters match the intended members (e.g., Version, GLaccount, DataSource, `#` members).

---

#### M1-02 — Implement `fetch_timeseries()` using the locked slice + pagination
- **Status:** DONE
- **Owner (Dev):** Backend Dev (Python)
- **QA:** QA Engineer
- **Description:** Implement a dedicated function that pulls the locked dataset slice, handles pagination/next links, and returns a dataframe with raw SAC fields.
- **Deliverable:** `sac_connector/timeseries.py` with:
  - `fetch_timeseries(provider_id, namespace_id="sac", ...)`
  - support for `$top` paging until done (or until max_rows limit)
  - safe timeouts + retries (reuse existing retry helper)
- **Definition of done:**
  - Function returns a dataframe with at least `Date` and selected measure column.
  - Pagination returns complete results (no duplicates due to paging logic).
  - Errors are actionable (include HTTP code + endpoint; no token/secret leakage).
- **What to test (QA):**
  - Unit tests with mocked HTTP:
    - two-page response merges correctly and deduplicates by full row signature
    - retry behavior on 429/5xx
  - Integration:
    - run function against real tenant → row count > 0 and stable between runs

---

#### M1-03 — Normalize to strict contract (ISO date + float value) and aggregate by month
- **Status:** DONE
- **Owner (Dev):** Data Dev (Python)
- **QA:** QA Engineer
- **Description:** Convert SAC `Date` (e.g., `YYYYMM`) to ISO date, coerce measure to float, and aggregate by month after filtering. Output columns: `date`, `value`, optional dims if needed.
- **Deliverable:** `pipeline/normalize_timeseries.py` + update `docs/data_contract.md` for this SAC dataset.
- **Definition of done:**
  - Output dataframe has columns `date` (YYYY-MM-DD) and `value` (float).
  - Aggregation rule implemented exactly as documented in `docs/dataset_binding.md`.
  - Deterministic output across repeated pulls (same filter + same cache).
- **What to test (QA):**
  - Unit:
    - `YYYYMM` parsing works and rejects invalid formats
    - aggregation produces one row per month
  - Integration:
    - run end-to-end pull + normalize → verify min/max date and no missing required fields

---

#### M1-04 — Wire `demo.refresh` to the locked series + cache outputs + metadata
- **Status:** DONE
- **Owner (Dev):** Backend Dev (Integration)
- **QA:** QA Lead
- **Description:** Make `python -m demo.refresh --source sac` use the timeseries pipeline and write cache + metadata (last refresh, row count, min/max date).
- **Deliverable:** updated `demo/refresh.py` + cache artifact in `data/cache/` (gitignored)
- **Definition of done:**
  - `python -m demo.refresh --source sac` produces cached normalized dataset and metadata.
  - If SAC fails, it falls back to last cache and warns.
  - If SAC returns empty series, it exits non-zero with a clear message pointing to `docs/dataset_binding.md`.
- **What to test (QA):**
  - Integration:
    - success path (SAC ok) creates/updates cache and prints summary
    - failure path (bad token) falls back to cache with warning
    - empty-series path (temporarily change filter) fails with actionable error

---

#### M1-05 — Add a minimal MCP server exposing `health` and `get_timeseries`
- **Status:** DONE
- **Owner (Dev):** Backend Dev (Platform)
- **QA:** QA Engineer
- **Description:** Implement a minimal MCP server exposing allow-listed tools only:
  - `health()` → returns tenant URL + provider ID + cache status (no secrets)
  - `get_timeseries(from_cache: bool=True, start: str|None=None, end: str|None=None)` → returns normalized series (and optionally refreshes if requested)
- **Deliverable:** `mcp_server/` (or `mcp_server.py`) runnable via:
  - `python -m mcp_server` (or documented command)
  - includes README snippet showing how to connect a client (tool listing)
- **Definition of done:**
  - Server starts and lists tools reliably.
  - `health` returns quickly (<1s from cache).
  - `get_timeseries` returns data from cache by default; optional refresh requires explicit flag.
  - Strict allow-list: no arbitrary URL fetching or raw query execution.
- **What to test (QA):**
  - Unit:
    - tool handlers validate inputs (date formats, max range)
  - Integration:
    - start server, call `health`, call `get_timeseries(from_cache=True)` → returns rows
    - call `get_timeseries(from_cache=False)` → triggers refresh once and returns rows

---

#### M1-06 — Add `demo.query` CLI for quick verification
- **Status:** DONE
- **Owner (Dev):** Backend Dev (Python)
- **QA:** QA Lead
- **Description:** Provide a tiny CLI that loads cached data and prints a one-screen summary (row count, min/max date, basic stats).
- **Deliverable:** `demo/query.py` runnable as `python -m demo.query`
- **Definition of done:**
  - CLI prints: row count, min/max date, first/last 3 rows, mean/median, and missing-value check.
  - Exits non-zero with actionable message if cache missing/corrupt.
- **What to test (QA):**
  - Offline: run after cache exists → prints summary
  - Negative: delete cache → confirms error message is clear

---

## Milestone Exit Criteria (M1)
- A documented “locked slice” query returns stable rows from SAC
- `demo.refresh` produces a normalized cached series conforming to the strict contract
- MCP server provides `health` and `get_timeseries` tools and works from cache by default
- All M1 tasks are `DONE` with QA sign-off

---

## Change Log (roadmap-impacting updates only)
- 2025-12-24: Added confirmed provider coordinates and MCP baseline milestone (M1) to support easy querying.
