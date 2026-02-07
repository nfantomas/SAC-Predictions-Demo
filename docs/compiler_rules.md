# Compiler rules (ScenarioIntent -> ScenarioParamsV3)

This document describes the deterministic mapping used by `scenarios/compiler_v3.py`.

## Defaults
- Ramp months:
  - policy: 3
  - target: 6
  - shock: 1
- Shock duration: 12 months if not provided.
- Severity bands (used when magnitude is missing):
  - operational: 5%
  - stress: 10%
  - crisis: 20%

## Intent type mapping

### constraint
- `keep_cost_flat` or `intent_type=constraint` → driver `cost_target`, `cost_target_pct=0.0`
- `keep_fte_flat` → driver `fte`, `growth_delta_pp_per_year = -BASELINE_FTE_GROWTH_YOY`

### policy (hiring freeze)
- driver `fte`
- default: `growth_delta_pp_per_year = -BASELINE_FTE_GROWTH_YOY`
- if a magnitude is provided: `fte_delta_pct = magnitude`, growth delta set to 0

### shock
- driver `cost`
- `impact_mode=level`, `impact_magnitude = magnitude`
- ramp = 1 month; duration = 12 months if not specified

### target
- driver `cost_target`
- `cost_target_pct = magnitude`
- ramp = max(6, timing.ramp_months)

### mix_shift / relocation
- driver `cost`
- `beta_multiplier = 1 + magnitude`, `impact_magnitude = 0`

### productivity / attrition
- driver `fte`
- `fte_delta_pct = magnitude`

## Timing
- `lag_months` is computed from `t0_start` to `timing.start` when available.
- If the start month is outside the horizon, compiler returns `needs_clarification=true`.

## Assumptions
- Fixed cost share ~20% at t0, beta inflates ~3%/yr.
- Baseline FTE growth ~3%/yr; templates adjust around this.
