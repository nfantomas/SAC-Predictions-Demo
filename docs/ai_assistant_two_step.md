# Two-step AI assistant (Interpreter → Compiler)

## Overview
The assistant is split into two phases to guarantee safe, deterministic behavior:
1) **Interpreter** converts free text into a structured `ScenarioIntent`.
2) **Compiler** converts `ScenarioIntent` into `ScenarioParamsV3` using templates.

The output then flows through:
`Normalize → Validate (fail-open) → Apply`.

## Architecture (high level)
- `llm/intent_interpreter.py` → `ScenarioIntent`
- `scenarios/compiler_v3.py` → `ScenarioParamsV3`
- `scenarios/normalize_params.py` → percent normalization
- `llm/validate_v3.py` → fail-open validation (errors only on invalid math)
- `scenarios/v3.py` → apply to cost/FTE series

## Schema versions
- ScenarioIntent: `intent_v1` (`llm/intent_schema.py`)

## Template mapping (summary)
See `docs/compiler_rules.md` for the full mapping table.

## Normalization rules
Percent-like fields are normalized when `abs(x) > 1.5`:
- `5` → `0.05`
- `-10` → `-0.10`

Each normalization produces a single warning per field.

## Severity tiers + caps
Severity is carried from the Interpreter into validation.
- **operational**: mild caps, conservative MoM.
- **stress**: wider CAGR and MoM caps.
- **crisis**: widest caps, still bounded.

Caps live in `config/validation_caps.py` and merge into `config.core.VALIDATION_CAPS`.

## Guardrail behavior
Fail-open means:
- **Block only** for invalid math (NaN/inf, negative cost/FTE, cost below alpha, impossible timing).
- **Warn** for aggressive growth, baseline deviation, or large monthly changes.

## Troubleshooting
Common issues:
- **Percent as whole number**: normalization warning appears; output still applies.
- **Timing beyond horizon**: compiler returns `needs_clarification=true`.

## Add a new intent
1) Extend `IntentType` in `llm/intent_schema.py`.
2) Add template logic in `scenarios/templates/` and wire in `scenarios/compiler_v3.py`.
3) Add fixtures in `tests/fixtures/intent_examples.json`.
4) Add acceptance prompt in `tests/fixtures/sample_prompts.json`.
