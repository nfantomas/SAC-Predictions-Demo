# Changelog

## Unreleased
- Added one-command Assistant V3 eval round output (`--out`) that now writes log + scorecard markdown/json, auto-loads prior benchmark if present, compares current vs benchmark in markdown (`current / benchmark`), and updates a tracked benchmark artifact at `evals/benchmark/assistant_v3_eval_benchmark.json`.
- Fixed SAC timeseries pagination to preserve duplicate-looking facts for correct monthly FTE aggregation.
- Switched SAC DES paging to server-driven nextLink without forced paging to keep totals consistent.
- Added OpenAI LLM provider with auto-selection and updated LLM tooling to support ChatGPT keys.
- Added FTE output mode and adjusted UI labels/KPIs to avoid summing headcount metrics.
- Simplified demo UI to a single combined chart placed above scenario controls.
- Hid SAC data details and sample rows behind expanders; removed narrative UI.
- Made Scenario Overrides collapsible to reduce visual clutter.
- Preserved SAC/fixture metadata on refresh so UI shows provider/metric/unit/currency.
- Tweaked refresh banner to a neutral caption (no warning highlight).
- Added cost↔FTE driver model with t0 mismatch guardrail, default assumptions, and V3 scenario presets with implied FTE cut messaging.
- Added scenario assistant V3 prompt/schema + check script, plus safety validator with bounds and projection clamp for LLM outputs.
- Added AI Scenario Assistant (V3) UI block with driver-aware apply pipeline, mismatch warning banner, and chart overlay alongside existing V2 flows.
- Documented scenario engine V3 (timeline, driver model, safety) and added offline smoke runner (`demo.scenario_smoke_v3`) that prints SCENARIO V3 SMOKE OK.
- Added V3 HR preset specs doc, preset factory, FTE cut planner, and apply_v3 support for beta multipliers, inflation, and cost targets.
- Wired V3 HR presets and cost-target plan into UI alongside legacy V2 presets; apply_v3 used for overlays.
- Added preset-mapping assistant (V3) with deterministic keyword routing, prompt template, and tests for mapping.
- Added scenario engine V3 schema/migration with ramp profiles and lag/onset/recovery timeline helper plus compatibility tests.
- Updated V3 presets to manager-friendly parameter bands with driver-consistent baseline math and Year-1 impact regression test.
- Simplified chart to show baseline + one preset/assistant line (optional custom), added KPI chips (t0, Year‑1/5/10 deltas, implied FTE), and surfaced alpha/beta/inflation assumptions.
- Refreshed V3 LLM prompt/schema with explicit alpha/beta/FTE/inflation assumptions, safety bounds, driver-aware params, and fenced-JSON rejection test for deterministic parsing.
- Added dedicated V3 LLM validator that clamps unsafe params (bounds + 10y multiplier + alpha floor) and raises on out-of-bounds projections with tests.
- Added pending-apply flow for V3 suggestions (no widget mutations), helper utilities, and tests so suggest→apply is stable and idempotent.
- Added M10 demo acceptance checklist covering baseline trend, presets, LLM assistant, guardrails, and SAC connectivity smokes.
- Added baseline growth defaults (6% YoY total with 3% inflation + 3% FTE growth components), config knobs, forecast floor enforcement, updated UI assumptions, and growth regression tests.
- Updated Hiring Freeze preset to model inflation-only growth (~3% YoY vs 6% baseline) with growth-delta handling in V3 apply and regression tests; validation now clamps extreme projections more robustly.

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

## Milestone M6 — Metric Mapping + LLM Reliability + UX Polish
- Added metric mapping and validated HR cost configuration with provider metadata.
- Reworked UI layout into Data/Forecast/Scenarios blocks and improved scenario presets.
- Strengthened Scenario Assistant prompts, schema validation, and consistency checks.
- Hardened Anthropic client parsing, model defaults, and max-token handling.
- Added debug outputs, demo script, and scenario validation warnings.
