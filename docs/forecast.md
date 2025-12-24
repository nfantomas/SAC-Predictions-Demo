# Baseline Forecast — Assumptions & Outputs

## Input contract
- Required columns: `date`, `value`
- Grain: monthly, `date` aligned to first of month (`YYYY-MM-01`)
- Source: cached normalized series (`data/cache/sac_export.csv`)

## Method selection (auto)
- **ETS** (Exponential Smoothing) is used when:
  - series is monthly
  - at least 24 points are available
- **Fallback:** damped CAGR is used when:
  - fewer than 24 points
  - ETS fit fails (single-line warning, no crash)

## Non-negativity
Forecast values are clipped at 0 to avoid negative headcount-style outputs.

## Output artifacts
- Forecast data: `data/cache/forecast.csv`
  - Columns: `date`, `yhat`, `method`
- Metadata: `data/cache/forecast_meta.json`
  - `generated_at`, `horizon_months`, `method_used`
  - `input_min_date`, `input_max_date`
  - `output_min_date`, `output_max_date`

## Quick verify checklist
1) Run refresh: `python -m demo.refresh --source sac`
2) Run forecast: `python -m demo.forecast`
3) Check:
   - `forecast.csv` has **120 rows** (10y horizon)
   - `output_min_date` is the month after `input_max_date`
   - `output_max_date` is 120 months after `output_min_date`
   - `yhat` values are non-negative

## Notes
- Forecast is deterministic (no randomness); same inputs produce same outputs.
- Horizon is 120 months by default; configurable in `pipeline/forecast_runner.py`.
