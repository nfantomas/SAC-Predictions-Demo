# Two-step assistant acceptance suite

This suite validates the Interpreter → Compiler → Validate → Apply pipeline with a fixed set of prompts.

## Run locally
```bash
poetry run pytest -q tests/acceptance/test_two_step_pipeline.py
```

## What it checks
- At least 25 prompts are exercised.
- Each prompt yields either:
  - an applied scenario, or
  - one clarifying question.
- No NaN/negative values in the applied series.
- For shock/target/policy intents, the scenario deviates from baseline by at least 2% at the start month.
