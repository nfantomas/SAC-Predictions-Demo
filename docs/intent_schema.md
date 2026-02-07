# ScenarioIntent schema (intent_v1)

This schema captures user intent and timing without requiring numeric curve parameters.

## Fields
- `schema_version`: fixed value `"intent_v1"`.
- `intent_type`: one of `constraint|shock|policy|target|mix_shift|productivity|attrition|relocation|other`.
- `driver`: `auto|cost|fte|cost_target`.
- `direction`: `increase|decrease|hold|unknown`.
- `magnitude`: `{ "type": "pct|abs|yoy_cap|none", "value": float|null }`
- `timing`: `{ "start": "YYYY-MM", "duration_months": int|null, "ramp_months": int }`
- `constraints`: list of strings (allowlist terms in prompts like `no_layoffs`, `keep_cost_flat`, `keep_fte_flat`).
- `entities`: `{ "regions": string[]|null, "population": "global"|null }`
- `severity`: `operational|stress|crisis`
- `confidence`: `low|medium|high`
- `need_clarification`: boolean
- `clarifying_question`: string|null

## Examples

1) Hiring freeze (policy)
```json
{
  "schema_version": "intent_v1",
  "intent_type": "policy",
  "driver": "auto",
  "direction": "hold",
  "magnitude": { "type": "none", "value": null },
  "timing": { "start": "2028-01", "duration_months": 12, "ramp_months": 3 },
  "constraints": ["no_layoffs"],
  "entities": { "regions": null, "population": "global" },
  "severity": "operational",
  "confidence": "high",
  "need_clarification": false,
  "clarifying_question": null
}
```

2) Cost target (target)
```json
{
  "schema_version": "intent_v1",
  "intent_type": "target",
  "driver": "cost_target",
  "direction": "decrease",
  "magnitude": { "type": "pct", "value": -0.1 },
  "timing": { "start": "2027-07", "duration_months": null, "ramp_months": 6 },
  "constraints": [],
  "entities": { "regions": ["EU"], "population": null },
  "severity": "stress",
  "confidence": "medium",
  "need_clarification": false,
  "clarifying_question": null
}
```

3) Geopolitical shock (shock)
```json
{
  "schema_version": "intent_v1",
  "intent_type": "shock",
  "driver": "auto",
  "direction": "decrease",
  "magnitude": { "type": "pct", "value": -0.2 },
  "timing": { "start": "2029-01", "duration_months": 12, "ramp_months": 1 },
  "constraints": [],
  "entities": { "regions": ["EU"], "population": null },
  "severity": "crisis",
  "confidence": "medium",
  "need_clarification": false,
  "clarifying_question": null
}
```

4) Keep costs flat (constraint)
```json
{
  "schema_version": "intent_v1",
  "intent_type": "constraint",
  "driver": "cost",
  "direction": "hold",
  "magnitude": { "type": "yoy_cap", "value": 0.0 },
  "timing": { "start": "2028-01", "duration_months": null, "ramp_months": 3 },
  "constraints": ["keep_cost_flat"],
  "entities": { "regions": null, "population": "global" },
  "severity": "operational",
  "confidence": "high",
  "need_clarification": false,
  "clarifying_question": null
}
```

5) Need clarification (other)
```json
{
  "schema_version": "intent_v1",
  "intent_type": "other",
  "driver": "auto",
  "direction": "unknown",
  "magnitude": { "type": "none", "value": null },
  "timing": { "start": "2028-01", "duration_months": null, "ramp_months": 3 },
  "constraints": [],
  "entities": { "regions": null, "population": "global" },
  "severity": "operational",
  "confidence": "low",
  "need_clarification": true,
  "clarifying_question": "Do you want a temporary shock or a permanent change?"
}
```
