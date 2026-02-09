# Scenario Engine V3 Knob Support

This checklist tracks which `ScenarioParamsV3` knobs are actively applied by the projection engine (`apply_scenario_v3_simple`) and are therefore safe to encourage in the prompt.

## Supported Now

- `driver`: `cost`, `fte`, `cost_target`
- `lag_months`
- `onset_duration_months`
- `shape`: `step`, `linear`, `exp`
- `impact_mode="level"` via `impact_magnitude`
- `growth_delta_pp_per_year`
- `drift_pp_per_year`
- `beta_multiplier`
- `fte_delta_pct`
- `fte_delta_abs`
- `cost_target_pct`
- `event_duration_months`
- `recovery_duration_months`
- `event_growth_delta_pp_per_year`
- `event_growth_exp_multiplier`
- `post_event_growth_pp_per_year`

## Prompt Alignment Rule

- Prompt guidance should only promote knobs listed as supported above.
- If a knob becomes partially implemented or regresses, prompt defaults must be tightened back to `0`/`null` for that knob until behavior is restored.
- Re-check this file whenever `scenarios/v3.py` or `scenarios/apply_scenario_v3.py` changes.
