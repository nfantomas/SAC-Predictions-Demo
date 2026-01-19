# Demo Acceptance Checklist (M10)

Use this as the QA/runbook to validate the demo end-to-end. Run in fixture/offline mode unless SAC connectivity is needed for a specific check.

## Pre-flight
- `poetry install` (once).
- Ensure `.env` is loaded (no secrets in repo); set `LLM_PROVIDER`/keys only if LLM calls are needed.
- Refresh artifacts if desired: `poetry run python -m demo.refresh` (uses SAC or fixture depending on env).

## Automated smokes
- Baseline + scenarios engine: `poetry run python -m demo.scenario_smoke_v3` (expect `SCENARIO V3 SMOKE OK`).
- LLM prompt/schema health: `poetry run python -m demo.llm_scenario_check_v3` (expect parsed JSON and `LLM OK (scenario v3)`; fails fast on bad schema/fenced output).
- Full test suite (optional for acceptance): `poetry run pytest -q` (should pass).

## UI smoke (Streamlit)
1) Start app: `poetry run streamlit run app.py`.
2) Confirm “Forecast view” shows only: Actuals, Baseline, and at most one V3 overlay (plus optional “Custom override” if toggled).
3) Verify KPI chips update when selecting presets/assistant overlay: t0 cost, Year‑1/5/10 deltas (% vs base), implied FTE change.
4) Assumptions caption shows alpha ≈ 2M, beta ≈ 10k, t0 FTE ≈ 800, baseline inflation ~3%/yr.
5) Boundary between actuals/forecast is present (vertical rule at last actual).

## Baseline acceptance
- Using fixture data, baseline should trend upward (~6%/yr). No downward drift unless actuals force it.
- Last actual value is respected; no negative values or cost below alpha.

## Preset acceptance (V3)
- Select each preset; ensure Year‑1 impact matches direction/magnitude band and slope stays parallel afterward:
  - Hiring freeze: near-baseline cost; flat growth change.
  - Convert IT contractors: ~1.5–2.5% dip Year‑1; parallel slope below baseline.
  - Inflation shock: ~4–6% lift Year‑1; higher level, same slope.
  - Outsource 120 UK→CZ: ~4–6% savings; ramped 6–12m; parallel slope lower.
  - Reduce cost 10%: cost aligns to target and resumes 3% growth; implied FTE cut shown.
- No preset drives cost below alpha; no extreme spikes.

## LLM assistant acceptance (V3)
- Get suggestion → validation happens; fenced/markdown JSON is rejected with a clear error.
- Pending suggestion shows rationale, safety warnings/adjustments, and params table; “Apply suggestion (V3)” uses a form and succeeds without Streamlit errors.
- Applied overlay label updates; KPIs/legend refresh correctly.

## Guardrails
- t0 mismatch warning appears if observed t0 differs >20%; alpha/beta recompute uses observed cost.
- 10y multiplier clamp: extreme inputs are clamped or rejected with a warning; alpha floor enforced (no cost < alpha).
- No widget key mutations when applying suggestions; repeated suggest→apply cycles do not crash.

## SAC connectivity (if required)
- `poetry run python -m demo.auth_check` and `poetry run python -m demo.des_check` succeed against the configured tenant.
- Refresh banner indicates cache use vs live pull; metadata panel shows provider/metric/unit/currency.
