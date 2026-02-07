# QA runbook: Two-step AI assistant

## Acceptance tests
Run:
```bash
poetry run pytest -q tests/acceptance/test_two_step_pipeline.py
```

Expected:
- all prompts either apply or request one clarification
- no unhandled exceptions

## UI checks (5–10 minutes)
1) Launch app: `poetry run streamlit run app.py`
2) In “AI scenario assistant (two-step)”:
   - enter prompt → click “Interpret & compile”
   - confirm intent summary + assumptions
   - edit parameters and apply
   - see chart update or single clarification question
3) Confirm warnings are summarized (≤5) and details appear in the expander.

## Add a new regression prompt
1) Add an entry to `tests/fixtures/sample_prompts.json`:
   - include `id`, `prompt`, and `expected.intent`
2) Re-run the acceptance test.
