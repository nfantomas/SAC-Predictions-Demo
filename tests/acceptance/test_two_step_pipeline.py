import json
from pathlib import Path

import pandas as pd

from llm.intent_interpreter import interpret_intent
from llm.intent_schema import ScenarioIntent
from llm.validate_v3 import ValidateContext, validate_and_sanitize_result
from scenarios.compiler_v3 import compile_intent
from scenarios.v3 import DriverContext, apply_scenario_v3_simple
from ui.warnings import summarize_warnings


def _baseline(months: int = 120, start: str = "2028-01-01") -> pd.DataFrame:
    dates = pd.date_range(start, periods=months, freq="MS")
    growth = (1.03) ** (pd.Series(range(months)) / 12.0)
    yhat = 10_000_000.0 * growth
    return pd.DataFrame({"date": dates.date.astype(str), "yhat": yhat})


def _month_diff(t0_start: str, start: str) -> int:
    t0 = pd.to_datetime(t0_start)
    target = pd.to_datetime(start)
    return (target.year - t0.year) * 12 + (target.month - t0.month)


def test_two_step_pipeline_acceptance(monkeypatch):
    prompts = json.loads(Path("tests/fixtures/sample_prompts.json").read_text())
    assert len(prompts) >= 25
    base = _baseline()
    ctx = DriverContext(alpha=2_000_000, beta0=10_000)
    t0_start = "2028-01"

    intent_map = {item["prompt"]: item["expected"]["intent"] for item in prompts}

    def fake_call_llm(system, user):
        for prompt, payload in intent_map.items():
            if prompt in system:
                return payload
        return {
            "schema_version": "intent_v1",
            "intent_type": "other",
            "driver": "auto",
            "direction": "unknown",
            "magnitude": {"type": "none", "value": None},
            "timing": {"start": "2028-01", "duration_months": None, "ramp_months": 3},
            "constraints": [],
            "entities": {"regions": None, "population": "global"},
            "severity": "operational",
            "confidence": "low",
            "need_clarification": True,
            "clarifying_question": "Please clarify the intent.",
        }

    monkeypatch.setattr("llm.intent_interpreter._call_llm", fake_call_llm)

    for item in prompts:
        intent_result = interpret_intent(item["prompt"], {"last_date": "2027-12"})
        intent = ScenarioIntent.model_validate(intent_result["intent"])
        compiled = compile_intent(intent, t0_start=t0_start, horizon_months=len(base))
        applied = False
        if compiled.needs_clarification:
            assert compiled.clarifying_question
        else:
            applied = True

        params = compiled.params_v3
        _, _, result = validate_and_sanitize_result(params.__dict__, ctx=ValidateContext())
        assert result.errors == []

        scenario = apply_scenario_v3_simple(base, params, context=ctx, horizon_months=len(base))
        assert scenario["yhat"].notna().all()
        assert (scenario["yhat"] >= 0).all()

        warning_msgs = [w.message for w in result.warnings]
        clamp_msgs = [c.message for c in result.clamps]
        summary, _ = summarize_warnings(warning_msgs, clamp_msgs, [])
        assert len(summary) <= 5

        intent_type = intent.intent_type
        if intent_type in ("shock", "target", "policy", "constraint"):
            start_idx = max(0, _month_diff(t0_start, intent.timing.start))
            start_idx = min(start_idx, len(base) - 1)
            end_idx = min(len(base), start_idx + 12)
            window = scenario["yhat"].iloc[start_idx:end_idx].reset_index(drop=True)
            baseline_window = base["yhat"].iloc[start_idx:end_idx].reset_index(drop=True)
            max_delta = ((window / baseline_window) - 1.0).abs().max()
            assert max_delta >= 0.02

        assert applied or (intent.need_clarification and intent.clarifying_question)
