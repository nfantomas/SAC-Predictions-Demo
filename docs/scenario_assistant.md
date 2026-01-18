# Scenario Assistant

## Purpose
The Scenario Assistant converts macro text (e.g., “trade wars erupt”) into HR cost scenario parameters and a human-readable rationale. It uses an LLM when enabled and falls back to deterministic rules when not.

## Mental model (macro -> HR costs)
- Trade wars / sanctions: inflation + supply chain costs -> wage pressure, hiring freeze, restructuring.
- AI productivity leap: automation or productivity -> either slower headcount growth (lower HR cost growth) or higher HR costs from upskilling.
- Reconciliation / tariffs easing: lower inflation pressure -> stabilization, moderate growth.

## Response schema (strict JSON)
```json
{
  "params": {
    "preset_base": null,
    "growth_delta_pp_per_year": 0.0,
    "shock_start_year": null,
    "shock_pct": 0.0,
    "shock_duration_months": null,
    "drift_pp_per_year": 0.0
  },
  "rationale": {
    "summary": "string (2–4 sentences)",
    "drivers": ["bullet string", "bullet string"],
    "assumptions": ["bullet string", "bullet string"],
    "confidence": "low|medium|high",
    "checks": {
      "text_sentiment": "upside|downside|neutral",
      "param_consistency": "ok|corrected"
    }
  }
}
```

## Consistency rules
- Upside text (growth, boom, recovery, reconciliation) should not yield negative growth unless the rationale clearly states automation-driven cost reduction.
- Downside text (war, recession, sanctions) may yield negative growth and/or a negative shock.
- shock_start_year must be a calendar year within the forecast horizon.

## Debugging
Enable “Debug LLM payload” in the UI to see:
- LLM request payload (model, max_tokens, prompts)
- LLM response (params + rationale)

## LLM configuration
- `LLM_PROVIDER=anthropic` with `ANTHROPIC_API_KEY=...` (optional `ANTHROPIC_MODEL`).
- If `LLM_PROVIDER` is unset, Anthropic is used when a key is present.

## CLI checks
- `poetry run python -m demo.llm_check`
- `poetry run python -m demo.llm_scenario_check`
