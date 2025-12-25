# Narrative Generation

## Inputs
- `series_df` with `date`, `value` (cached normalized series only)
- Scenario parameters (growth delta, shock year/pct, drift)
- Optional market indications text (free-form)

## Outputs
`generate_narrative(...)` returns:
- `mode`: `template` or `llm`
- `title`: short heading
- `summary`: short paragraph
- `bullets`: 3–5 bullet points
- `assumptions`: one-line disclaimer
- optional `reason` when falling back to template

## Safety constraints
- **No row-level data** is passed to the LLM path.
- Template mode is always available and deterministic.

## Fallback behavior
- If `use_llm=true` but `NARRATIVE_LLM_KEY` is missing:
  - `mode="template"` with `reason="missing_llm_key"`

## Quick verify
1) Ensure cached series exists: `python -m demo.refresh --source fixture`
2) Run narrative generation in the app or via `demo.smoke_app`
