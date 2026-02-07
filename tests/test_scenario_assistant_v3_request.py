from llm.provider import LLMError
from llm.scenario_assistant_v3 import request_suggestion


def test_request_suggestion_retries_on_http_400(monkeypatch):
    calls = {"n": 0}

    def fake_generate_json(system_prompt, user_prompt, schema_hint=None):
        calls["n"] += 1
        if calls["n"] == 1:
            raise LLMError("llm_http_400")
        return {
            "scenario_driver": "auto",
            "suggested_driver": "cost",
            "params": {
                "driver": "cost",
                "lag_months": 0,
                "onset_duration_months": 0,
                "event_duration_months": None,
                "recovery_duration_months": None,
                "shape": "linear",
                "impact_mode": "level",
                "impact_magnitude": 0.0,
                "growth_delta_pp_per_year": 0.0,
                "drift_pp_per_year": 0.0,
                "event_growth_delta_pp_per_year": None,
                "event_growth_exp_multiplier": None,
                "post_event_growth_pp_per_year": None,
                "fte_delta_abs": None,
                "fte_delta_pct": None,
                "beta_multiplier": None,
                "cost_target_pct": 0.0,
            },
            "rationale": {"title": "t", "summary": "s", "assumptions": [], "why_these_numbers": [], "sanity_checks": {"ten_year_multiplier_estimate": 1.0, "notes": "ok"}},
            "safety": {"adjustments": [], "warnings": []},
        }

    monkeypatch.setattr("llm.scenario_assistant_v3.generate_json", fake_generate_json)
    out = request_suggestion("hiring freeze from 2028", horizon_years=10, baseline_stats={"last_value": 1})
    assert out["response"]["suggested_driver"] == "cost"
    assert out["fallback_used"] is True
    assert calls["n"] == 2


def test_request_suggestion_raises_non_400(monkeypatch):
    def fake_generate_json(system_prompt, user_prompt, schema_hint=None):
        raise LLMError("llm_timeout")

    monkeypatch.setattr("llm.scenario_assistant_v3.generate_json", fake_generate_json)

    try:
        request_suggestion("x", horizon_years=10, baseline_stats={"last_value": 1})
    except LLMError as exc:
        assert str(exc) == "llm_timeout"
    else:
        raise AssertionError("Expected LLMError")
