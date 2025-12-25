# Scenario Presets

Scenarios are overlays on the baseline forecast (`yhat`). They do **not**
re-fit the model.

## Overlay parameters (v2)
- `growth_delta_pp_per_year`: constant delta to yearly growth (percentage points)
- `shock_start_year`: year when a level change starts (inclusive)
- `shock_pct`: level multiplier during shock (e.g., -0.08 = -8%)
- `shock_duration_months`: duration in months; `0` or `None` means permanent
- `drift_pp_per_year`: linear drift to growth over time (annual pp / 12 monthly)

All scenario outputs are clipped at 0.0.

## Preset table
| name | growth_delta_pp_per_year | shock_start_year | shock_pct | shock_duration_months | drift_pp_per_year | story |
|---|---:|---:|---:|---:|---:|---|
| base | 0.00 | — | 0.00 | — | 0.00 | Baseline HR cost outlook. |
| trade_war_downside | -0.03 | 2027 | -0.08 | 0 | 0.00 | Trade-war shock with lasting step-down and slower growth. |
| growth_upside | 0.03 | — | 0.00 | — | 0.00 | Higher growth due to expansion and hiring. |
| aging_pressure | 0.00 | — | 0.00 | — | -0.02 | Aging workforce slowly reduces growth over time. |

## Interpretation
- `shock_start_year` applies for `shock_duration_months` (or permanent if 0/None).
- `growth_delta_pp_per_year` affects every month’s growth rate.
- `drift_pp_per_year` accumulates linearly over time.
