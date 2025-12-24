# Scenario Presets

Scenarios are overlays on the baseline forecast (`yhat`). They do **not**
re-fit the model.

## Overlay parameters
- `growth_delta_pp`: constant delta to monthly growth (percentage points)
- `shock_year`: year when a permanent level change starts (inclusive)
- `shock_pct`: level multiplier from `shock_year` onward (e.g., -0.08 = -8%)
- `drift_pp_per_year`: linear drift to growth over time (annual pp / 12 monthly)

All scenario outputs are clipped at 0.0.

## Preset table
| name | growth_delta_pp | shock_year | shock_pct | drift_pp_per_year | story |
|---|---:|---:|---:|---:|---|
| base | 0.00 | — | 0.00 | 0.00 | Keep baseline assumptions unchanged. |
| downside_trade_war | -0.01 | 2027 | -0.08 | 0.00 | Trade-war style shock with lasting step-down. |
| upside | 0.01 | — | 0.00 | 0.00 | Higher growth due to favorable macro conditions. |
| aging_drift | 0.00 | — | 0.00 | -0.02 | Aging workforce slowly reduces growth over time. |

## Interpretation
- `shock_year` is **permanent**: all months in that year and onward are scaled.
- `growth_delta_pp` affects every month’s growth rate.
- `drift_pp_per_year` accumulates linearly over time.
