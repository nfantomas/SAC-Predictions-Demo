# Changelog

## Milestone M0 — Setup & Access
- Added SAC access checklist and updated OAuth/DES connectivity guidance.
- Implemented OAuth client-credentials auth with masking and auth/DES checks.
- Added SAC export client with pagination, retries, normalization, and refresh CLI.
- Implemented cache layer with metadata and cache fallback behavior.
- Defined data contract and fixture dataset with fixture-based tests.
- Added tooling: Poetry config, lockfile, smoke test, lint/test commands, and Makefile.

## Milestone M1 — Dataset Binding + MCP Baseline
- Documented locked slice query for the SAC provider and aggregation rule.
- Implemented timeseries fetch with pagination, dedup, and retries.
- Added strict normalization and SAC-specific contract mapping.
- Wired refresh to the locked slice with cache metadata and fallback messaging.
- Added minimal MCP server with health and get_timeseries endpoints.
- Added demo.query CLI summary for cached data.

## Milestone M2 — Baseline Forecast (10y)
- Implemented ETS baseline with damped CAGR fallback and deterministic outputs.
- Added forecast runner + CLI with cache artifacts and metadata.
- Added one-command demo path (refresh → forecast) with cache fallback.
- Documented forecast assumptions and verification checklist.
- Added fixture-based refresh path for offline forecast QA.

## Milestone M3 — Scenarios (3–5 presets)
- Added scenario overlay v2 with pp/year controls, shocks, drift, and stability bounds.
- Implemented business-first presets and scenarios runner with cache outputs.
- Added scenario CLI and tests for overlay behavior and presets.

## Milestone M4 — UI + Narrative
- Streamlit UI redesign for HR cost forecasting with provenance panel and KPI cards.
- Added actual/forecast boundary and preset scenario comparison charts.
- Narrative generation updated for HR cost language with template fallback.

## Milestone M5 — HR Cost Clarity + Scenario Assistant
- Implemented HR cost series mapping, provenance metadata, and fixture pipeline.
- Added Scenario Assistant with LLM integration, rationale schema, and impact preview.
- Added Anthropic provider, health checks, and robust JSON parsing/validation.
- Added LLM debug tooling, scenario check CLI, and UI debug payload view.
