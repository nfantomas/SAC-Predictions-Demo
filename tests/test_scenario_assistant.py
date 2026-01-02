import pytest

from narrative.scenario_assistant import _build_prompts, suggest_scenario, validate_and_normalize_suggestion


def test_llm_missing_key_fallback(monkeypatch):
    monkeypatch.delenv("NARRATIVE_LLM_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    result = suggest_scenario("trade wars", 10, {}, use_llm=True)
    assert result["mode"] == "llm_error"
    assert result.get("error") == "missing_llm_key"


def test_invalid_llm_output_fallback(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "key")

    def fake_generate(*args, **kwargs):
        raise Exception("invalid_llm_output")

    monkeypatch.setattr("narrative.scenario_assistant.llm_generate", fake_generate)
    result = suggest_scenario("trade wars", 10, {}, use_llm=True)
    assert result["mode"] == "llm_error"
    assert result.get("error") == "invalid_llm_output"


def test_llm_uninformative_fallback(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
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

    monkeypatch.setattr("narrative.scenario_assistant.llm_generate", fake_generate)
    result = suggest_scenario("asteroid impact", 10, {}, use_llm=True)
    assert result["mode"] == "llm_error"
    assert result.get("error") == "llm_uninformative"


def test_prompt_has_no_example_payload():
    prompts = _build_prompts("test", 10, {"last_value": 1.0})
    assert "Example JSON" not in prompts["user"]


def test_llm_inconsistent_fallback(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
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

    monkeypatch.setattr("narrative.scenario_assistant.llm_generate", fake_generate)
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


def test_golden_scenario_outputs(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "key")

    def fake_generate(system_prompt, user_prompt, schema_hint=None):
        text = user_prompt.lower()
        if "trade wars erupt" in text:
            return {
                "params": {
                    "preset_base": "trade_war_downside",
                    "growth_delta_pp_per_year": -0.2,
                    "shock_start_year": 2026,
                    "shock_pct": -0.2,
                    "shock_duration_months": 12,
                    "drift_pp_per_year": -0.02,
                },
                "rationale": {
                    "summary": "Trade wars raise costs and slow hiring.",
                    "drivers": ["Tariff-driven inflation", "Hiring freeze pressure"],
                    "assumptions": ["Trade war persists for 12 months"],
                    "confidence": "medium",
                    "checks": {"text_sentiment": "downside", "param_consistency": "ok"},
                },
            }
        if "recession" in text:
            return {
                "params": {
                    "preset_base": None,
                    "growth_delta_pp_per_year": -0.15,
                    "shock_start_year": 2025,
                    "shock_pct": -0.1,
                    "shock_duration_months": 12,
                    "drift_pp_per_year": -0.01,
                },
                "rationale": {
                    "summary": "Recession leads to cost containment and slower growth.",
                    "drivers": ["Budget cuts", "Hiring slowdown"],
                    "assumptions": ["No immediate recovery"],
                    "confidence": "medium",
                    "checks": {"text_sentiment": "downside", "param_consistency": "ok"},
                },
            }
        if "ai boom" in text:
            return {
                "params": {
                    "preset_base": None,
                    "growth_delta_pp_per_year": 0.1,
                    "shock_start_year": None,
                    "shock_pct": 0.0,
                    "shock_duration_months": None,
                    "drift_pp_per_year": 0.0,
                },
                "rationale": {
                    "summary": "AI boom drives expansion and upskilling.",
                    "drivers": ["Productivity investments", "Talent upskilling"],
                    "assumptions": ["Demand stays strong"],
                    "confidence": "high",
                    "checks": {"text_sentiment": "upside", "param_consistency": "ok"},
                },
            }
        if "aging workforce" in text:
            return {
                "params": {
                    "preset_base": "aging_pressure",
                    "growth_delta_pp_per_year": 0.0,
                    "shock_start_year": None,
                    "shock_pct": 0.0,
                    "shock_duration_months": None,
                    "drift_pp_per_year": -0.02,
                },
                "rationale": {
                    "summary": "Demographics reduce growth over time.",
                    "drivers": ["Retirement wave", "Hiring friction"],
                    "assumptions": ["No major policy offsets"],
                    "confidence": "medium",
                    "checks": {"text_sentiment": "downside", "param_consistency": "ok"},
                },
            }
        return {
            "params": {
                "preset_base": None,
                "growth_delta_pp_per_year": -0.05,
                "shock_start_year": 2025,
                "shock_pct": -0.05,
                "shock_duration_months": 6,
                "drift_pp_per_year": 0.0,
            },
            "rationale": {
                "summary": "Restructuring cuts near-term costs.",
                "drivers": ["Layoffs", "Cost rationalization"],
                "assumptions": ["Limited rehiring"],
                "confidence": "medium",
                "checks": {"text_sentiment": "downside", "param_consistency": "ok"},
            },
        }

    monkeypatch.setattr("narrative.scenario_assistant.llm_generate", fake_generate)

    inputs = [
        "trade wars erupt between US and China",
        "global recession",
        "ai boom accelerates productivity",
        "aging workforce pressures hiring",
        "restructuring plan announced",
    ]
    for text in inputs:
        result = suggest_scenario(text, 10, {}, use_llm=True)
        assert result["mode"] == "llm"
        assert "params" in result and "rationale" in result
        assert result["rationale"]["summary"]
        assert result["rationale"]["drivers"]
        assert result["rationale"]["assumptions"]
