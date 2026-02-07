from llm.intent_schema import ScenarioIntent
from scenarios.compiler_v3 import compile_intent


def _intent_base(intent_type: str) -> dict:
    return {
        "schema_version": "intent_v1",
        "intent_type": intent_type,
        "driver": "auto",
        "direction": "decrease",
        "magnitude": {"type": "pct", "value": -0.1},
        "timing": {"start": "2028-01", "duration_months": 12, "ramp_months": 3},
        "constraints": [],
        "entities": {"regions": None, "population": "global"},
        "severity": "stress",
        "confidence": "medium",
        "need_clarification": False,
        "clarifying_question": None,
    }


def test_compiles_target_intent():
    intent = ScenarioIntent.model_validate(_intent_base("target"))
    result = compile_intent(intent, t0_start="2027-01")
    assert result.params_v3.driver == "cost_target"
    assert result.params_v3.cost_target_pct == -0.1


def test_compiles_shock_intent():
    intent = ScenarioIntent.model_validate(_intent_base("shock"))
    result = compile_intent(intent, t0_start="2027-01")
    assert result.params_v3.driver == "cost"
    assert result.params_v3.impact_mode == "level"


def test_compiles_policy_intent():
    intent = ScenarioIntent.model_validate(_intent_base("policy"))
    result = compile_intent(intent, t0_start="2027-01")
    assert result.params_v3.driver == "fte"


def test_constraint_keep_cost_flat():
    payload = _intent_base("constraint")
    payload["constraints"] = ["keep_cost_flat"]
    payload["direction"] = "hold"
    payload["magnitude"] = {"type": "none", "value": None}
    intent = ScenarioIntent.model_validate(payload)
    result = compile_intent(intent, t0_start="2027-01")
    assert result.params_v3.driver == "cost_target"
    assert result.params_v3.cost_target_pct == 0.0


def test_timing_out_of_horizon_sets_clarification():
    intent = ScenarioIntent.model_validate(_intent_base("target"))
    intent = ScenarioIntent.model_validate({**intent.model_dump(), "timing": {"start": "2028-03", "duration_months": 12, "ramp_months": 3}})
    result = compile_intent(intent, t0_start="2028-01", horizon_months=1)
    assert result.needs_clarification is True


def test_timing_before_horizon_sets_clarification_and_clamps_to_t0():
    intent = ScenarioIntent.model_validate(_intent_base("constraint"))
    intent = ScenarioIntent.model_validate(
        {**intent.model_dump(), "timing": {"start": "2027-01", "duration_months": None, "ramp_months": 3}}
    )
    result = compile_intent(intent, t0_start="2028-01", horizon_months=120)
    assert result.needs_clarification is True
    assert result.params_v3.lag_months == 0


def test_constraint_with_magnitude_compiles_to_target():
    payload = _intent_base("constraint")
    payload["constraints"] = ["no_layoffs"]
    payload["direction"] = "decrease"
    payload["magnitude"] = {"type": "pct", "value": -0.10}
    intent = ScenarioIntent.model_validate(payload)
    result = compile_intent(intent, t0_start="2028-01", horizon_months=120)
    assert result.params_v3.driver == "cost_target"
    assert result.params_v3.cost_target_pct == -0.10
    assert result.params_v3.onset_duration_months >= 12


def test_target_with_no_layoffs_uses_slow_ramp():
    payload = _intent_base("target")
    payload["constraints"] = ["no_layoffs"]
    payload["direction"] = "decrease"
    payload["magnitude"] = {"type": "pct", "value": -0.10}
    intent = ScenarioIntent.model_validate(payload)
    result = compile_intent(intent, t0_start="2028-01", horizon_months=120)
    assert result.params_v3.driver == "cost_target"
    assert result.params_v3.onset_duration_months >= 12
