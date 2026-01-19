# Scenario Engine V3 — Timeline + Driver Model + Safety

This doc describes the scenario overlay V3 used in the demo.

## Timeline
- **Lag** → **Onset** → **Event (active)** → **Recovery**.
- Shapes: `step`, `linear`, `exp` (normalized 0..1 via `profile_factor`).
- Durations: onset/recovery 0 = step; `None` event duration = permanent; `None` recovery = no recovery.
- Growth stack per month: baseline growth → `growth_delta_pp_per_year/12` → `drift_pp_per_year/12 * idx` → onset/recovery impact (level/growth mode) with ±50% MoM clamp and non-negative floor.

## Driver model (cost ↔ FTE)
- Formula: `TotalCost = alpha + beta * FTE`.
- Defaults (demo): t0 cost 10,000,000 EUR/month; fixed share 20%; t0 FTE 800 → alpha 2,000,000; beta 10,000.
- Implied FTE from cost: `max(0, (cost - alpha) / beta)`.
- Cost from FTE: `max(0, alpha + beta * fte)`.
- Driver options:
  - `cost`: overlay cost directly.
  - `fte`: convert baseline cost to implied FTE → overlay → convert back to cost.
  - `cost_target`: apply overlay on cost; implied FTE optional for display.

## t0 mismatch guardrail
- Compute observed t0 cost from last actual month in the app series.
- If `abs(observed - configured) / configured > 0.20`, use observed for alpha/beta and show:  
  “Assumption mismatch: observed t0 cost is X; using observed for alpha/beta.”

## Safety validator (LLM suggestions)
- Parameter bounds: `impact_magnitude` level ∈ [-0.5, 1.0]; growth ∈ [-0.5, 0.5]; `growth_delta_pp_per_year` ∈ [-0.5, 0.5]; `drift_pp_per_year` ∈ [-0.3, 0.3]; durations clamped to: lag [0,60], onset [0,24], event [0,120] or null, recovery [0,60] or null.
- Projection sanity: simulate 10y multiplier; clamp to keep within [0.2x, 3.0x] or reject if still out of range.

## UI notes
- V3 assistant lives alongside V2; applying V3 does not touch V2 overrides.
- Displays params table, rationale, alpha/beta card with t0 used, mismatch warning banner, and an “Implied FTE (derived)” label for driver conversions.
