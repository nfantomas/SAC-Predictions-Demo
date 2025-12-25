import pytest

from narrative.scenario_assistant import _build_prompts, suggest_scenario, validate_and_normalize_suggestion


def test_llm_missing_key_fallback(monkeypatch):
    monkeypatch.delenv("NARRATIVE_LLM_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    result = suggest_scenario("trade wars", 10, {}, use_llm=True)
    assert result["mode"] == "llm_error"
    assert result.get("error") == "missing_llm_key"


def test_invalid_llm_output_fallback(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "key")

    def fake_generate(*args, **kwargs):
        raise Exception("invalid_llm_output")

    monkeypatch.setattr("narrative.scenario_assistant.anthropic_generate", fake_generate)
    result = suggest_scenario("trade wars", 10, {}, use_llm=True)
    assert result["mode"] == "llm_error"
    assert result.get("error") == "invalid_llm_output"


def test_llm_uninformative_fallback(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "key")

    def fake_generate(*args, **kwargs):
        return {
            "params": {
                "growth_delta_pp_per_year": 0.0,
                "shock_start_year": None,
                "shock_pct": 0.0,
                "shock_duration_months": 12,
                "drift_pp_per_year": 0.0,
            },
            "rationale": {
                "summary": "no change",
                "drivers": [],
                "assumptions": [],
                "confidence": "low",
                "checks": {"text_sentiment": "downside", "param_consistency": "ok"},
            },
        }

    monkeypatch.setattr("narrative.scenario_assistant.anthropic_generate", fake_generate)
    result = suggest_scenario("asteroid impact", 10, {}, use_llm=True)
    assert result["mode"] == "llm_error"
    assert result.get("error") == "llm_uninformative"


def test_prompt_has_no_example_payload():
    prompts = _build_prompts("test", 10, {"last_value": 1.0})
    assert "Example JSON" not in prompts["user"]


def test_llm_inconsistent_fallback(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "key")

    def fake_generate(*args, **kwargs):
        return {
            "params": {
                "growth_delta_pp_per_year": -0.1,
                "shock_start_year": None,
                "shock_pct": 0.0,
                "shock_duration_months": None,
                "drift_pp_per_year": 0.0,
            },
            "rationale": {
                "summary": "Global boom lifts costs.",
                "drivers": ["Booming demand"],
                "assumptions": ["Stable inflation"],
                "confidence": "medium",
                "checks": {"text_sentiment": "upside", "param_consistency": "ok"},
            },
        }

    monkeypatch.setattr("narrative.scenario_assistant.anthropic_generate", fake_generate)
    result = suggest_scenario("huge global growth thanks to ai leap forward", 10, {}, use_llm=True)
    assert result["mode"] == "llm_error"
    assert result.get("error") == "llm_inconsistent"


def test_normalize_shock_pct_percent():
    params, consistency, warnings = validate_and_normalize_suggestion(
        {
            "growth_delta_pp_per_year": 0.1,
            "shock_start_year": None,
            "shock_pct": -25.0,
            "shock_duration_months": 12,
            "drift_pp_per_year": 0.0,
        },
        horizon_years=10,
    )
    assert params["shock_pct"] == pytest.approx(-0.25)
    assert consistency == "corrected"
    assert any("Normalized shock_pct" in item for item in warnings)
