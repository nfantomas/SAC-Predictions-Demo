# tasks.md — Demo Delivery Tasks (Developer Assignment Source of Truth)

## Workflow (rules)
- **Developers only take tasks listed here.** New work = new task in this file.
- Each task has: **Owner (Dev)** → **PR** → **QA (review + tests)** → **Done**.
- QA verifies:
  - unit tests where applicable
  - integration test / smoke run (end-to-end where relevant)
  - definition of done met
- **Milestone gating:** Only when all tasks in a milestone are **DONE** do we start the next milestone (by adding the next milestone section and tasks).
- **Roadblocks:** If any task is blocked by a missing assumption/constraint/API limitation, update **roadmap.md** (scope/architecture/risks) and note the change in the **Change Log** below.

---

## Status legend
- `NOT STARTED`
- `IN PROGRESS`
- `IN QA`
- `BLOCKED`
- `DONE`

---

## Milestone M0 — Setup & Access (Connectivity proven)
**Milestone goal:** SAC OAuth access works and a small dataset can be pulled reliably (even before UI/forecast).

### M0 Task List

#### M0-01 — Create SAC OAuth client & permissions checklist
- **Status:** DONE
- **Owner (Dev):** Dev Lead (Integration)
- **QA:** QA Lead
- **Description:** Define the exact SAC access prerequisites: OAuth client creation, required roles/scopes, tenant URL formats, and the precise export endpoint(s) used for the demo.
- **Deliverable:** `docs/access.md` with step-by-step checklist + “known-good” configuration values (placeholders, no secrets).
- **Definition of done:**
  - Document allows a second engineer to configure access on a fresh tenant without additional context.
  - Includes: required SAC roles/permissions, auth/token endpoint(s), base URL patterns, and export endpoint(s) used by code.
  - Includes a short “common failures” section (401/403/404/429) with likely causes.

**What to test (QA):**
- Documentation test: follow `docs/access.md` from scratch and confirm you can obtain a token and call a “whoami”/test endpoint (or export endpoint with minimal query).
- Repo scan: verify no secrets are committed (grep for `client_secret`, `Authorization:` strings).

---

#### M0-02 — Implement token acquisition (client credentials) + secure config loading
- **Status:** DONE
- **Owner (Dev):** Backend Dev (Python)
- **QA:** QA Engineer
- **Description:** Implement OAuth client-credentials token flow and config loading from environment variables (with optional `.env` for local).
- **Deliverable:** `sac_connector/auth.py`, `demo/auth_check.py`, `config.py`, `.env.example`
- **Definition of done:**
  - `python -m demo.auth_check` prints `OK` + token expiry timestamp.
  - Missing/invalid env vars produce actionable errors (which variable, expected format).
  - No secrets are printed to logs (masking applied).

**What to test (QA):**
- Unit tests (offline):
  - Config validation: missing env var → raises `ConfigError` with clear message.
  - Logging: ensure secret values are masked (assert log output does not contain secret).
- Integration (requires SAC):
  - With valid env vars: `python -m demo.auth_check` exits code 0 and shows expiry.
  - With invalid secret: exits non-zero and prints a single-line actionable error.

---

#### M0-03 — Implement minimal SAC export pull (small dataset) + pagination/retry
- **Status:** DONE
- **Owner (Dev):** Backend Dev (Integration)
- **QA:** QA Engineer
- **Description:** Implement a minimal data pull that fetches a small time series from SAC export API with basic filters and chosen grain.
- **Deliverable:** `sac_connector/export.py`, `demo/refresh.py` writing normalized cache to `data/cache/`
- **Definition of done:**
  - `python -m demo.refresh --source sac` completes end-to-end after env config.
  - Supports pagination if API returns continuation/next links.
  - Retries transient errors (429/5xx) with exponential backoff + max attempts.
  - Output schema normalized to columns:
    - `date` (ISO, aligned to grain)
    - `value` (float)
    - optional `dim_*` (string)
  - Outputs are deterministic and idempotent (rerun does not duplicate rows).

**What to test (QA):**
- Unit tests (offline with mocked HTTP):
  - Pagination: mock 2-page response → combined rows count equals sum.
  - Retry: simulate 429 then 200 → succeeds and sleeps/backoff invoked (mock time).
  - Normalization: input payload → output dataframe has required columns + correct dtypes.
- Integration (requires SAC):
  - Run: `python -m demo.refresh --source sac` → file created + row count > 0.
  - Rerun immediately → row count unchanged (no duplicates) and latest date stable.

---

#### M0-04 — Cache layer (read/write) + “use cache on failure” behavior
- **Status:** DONE
- **Owner (Dev):** Backend Dev (Data)
- **QA:** QA Engineer
- **Description:** Add cache API so demos don’t depend on SAC availability. Cache should store dataset + metadata.
- **Deliverable:** `pipeline/cache.py` + fallback logic in `demo/refresh.py`
- **Definition of done:**
  - Cache supports `save_cache(df, meta)` and `load_cache()` returning both.
  - Metadata includes: `last_refresh_time`, `source`, `row_count`, `min_date`, `max_date`.
  - If SAC pull fails, refresh uses last cache and emits a clear warning message (stdout + UI-ready string).

**What to test (QA):**
- Unit tests (offline):
  - Save then load → dataframe equality (values + schema) and metadata fields present.
  - Corrupt/empty cache → load raises clear error with remediation steps.
- Integration:
  - Populate cache once.
  - Break SAC auth (set bad secret) and run refresh → succeeds using cache + emits warning.

---

#### M0-05 — Define demo dataset contract + sample dataset fixture
- **Status:** DONE
- **Owner (Dev):** Data Dev (Python)
- **QA:** QA Lead
- **Description:** Formalize data contract and provide a fixture for offline development and repeatable tests.
- **Deliverable:** `docs/data_contract.md`, `tests/fixtures/sample_series.csv`
- **Definition of done:**
  - Contract specifies required fields, grain rules, allowed dims, and missing-value policy.
  - Fixture conforms to contract and passes normalization pipeline.
  - Tests can run without SAC using fixture only.

**What to test (QA):**
- Documentation review: contract matches actual output of `demo.refresh` normalization.
- Unit test: fixture loads → normalization produces valid schema and no NaNs in required fields.

---

#### M0-06 — Repo bootstrap: lint, formatting, tests, and one-command smoke run
- **Status:** DONE
- **Owner (Dev):** DevOps Dev (Python Tooling)
- **QA:** QA Engineer
- **Description:** Establish minimal engineering hygiene so later milestones are fast and safe.
- **Deliverable:** dependency management (`pyproject.toml` or `requirements.txt`), `pytest` setup, linter/formatter (e.g., ruff), `demo/smoke.py`, optional CI workflow.
- **Definition of done:**
  - `pytest` passes locally using fixture dataset (no SAC needed).
  - `python -m demo.smoke` runs end-to-end: load fixture → normalize → save cache → print `SMOKE OK`.
  - Lint/format command documented in README and runs cleanly.

**What to test (QA):**
- Run commands on a clean checkout:
  - `python -m venv .venv && pip install -r requirements.txt` (or equivalent)
  - `pytest -q` → all green
  - `python -m demo.smoke` → outputs `SMOKE OK`
- If CI present: open PR → confirm checks run and pass.

---

## Milestone Exit Criteria (M0)
- Token check passes against SAC tenant using OAuth client credentials.
- Refresh pulls a real SAC dataset and writes a normalized cached dataset.
- Offline fixture mode supports repeatable tests (no SAC required).
- All M0 tasks are `DONE` with QA sign-off.

---

# Task Definition — Poetry + Virtual Environment Setup

Copy-paste this task into `tasks.md` under Milestone **M0** (or replace parts of M0-06 if you want to merge tooling tasks).

---

#### M0-07 — Add Poetry dependency management + local venv workflow
- **Status:** DONE
- **Owner (Dev):** DevOps Dev (Python Tooling)
- **QA:** QA Engineer
- **Description:** Standardize Python dependency management with **Poetry** and ensure developers can create and use an isolated **virtual environment** consistently (prefer in-project `.venv`). This must support offline test runs using the fixture dataset and be compatible with later Docker packaging.
- **Deliverable:**
  - `pyproject.toml` (Poetry project definition)
  - `poetry.lock`
  - `.env.example` retained (Poetry must not require secrets to install)
  - `README.md` updates: install + venv + run commands
  - Optional but recommended: `Makefile` or `scripts/dev.sh` with common commands

- **Definition of done:**
  - A clean checkout can be set up with exactly:
    - `poetry --version` (Poetry installed)
    - `poetry config virtualenvs.in-project true`
    - `poetry install`
  - Project creates/uses a local venv at `./.venv/` (or clearly documented alternative if not feasible).
  - The following commands work from the Poetry environment:
    - `poetry run pytest -q` (offline, uses fixtures only)
    - `poetry run python -m demo.smoke` prints `SMOKE OK`
  - Dependency groups are organized (at minimum):
    - `main` (runtime)
    - `dev` (test/lint tooling)
  - No dependency installation step requires SAC credentials or network calls beyond standard package install.
  - All new commands are documented in `README.md` with copy-paste snippets.

**What to test (QA):**
- On a clean machine/clean checkout (no prior venv):
  1) `poetry config virtualenvs.in-project true`
  2) `poetry install`
  3) Verify `.venv/` directory exists
  4) `poetry run pytest -q` → all tests pass (no SAC required)
  5) `poetry run python -m demo.smoke` → outputs `SMOKE OK`
- Verify lockfile consistency:
  - `poetry check` and `poetry lock --check` (or equivalent) succeed
- Verify secrets hygiene:
  - `git grep -n "client_secret\|Authorization: Bearer\|SAC_CLIENT_SECRET"` returns nothing (except docs explaining env vars)


## Change Log (roadmap-impacting updates only)
- (empty)

---

## Template (copy for next milestone)
> ### Milestone Mx — <Name>
> **Goal:** …
> #### Mx-01 — <Task title>
> - **Status:** NOT STARTED
> - **Owner (Dev):**
> - **QA:**
> - **Description:**
> - **Deliverable:**
> - **Definition of done:**
> **What to test (QA):**
