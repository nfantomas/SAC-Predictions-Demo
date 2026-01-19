from llm.scenario_assistant_v3 import build_prompts


def test_prompt_template_formats_without_keyerror():
    prompts = build_prompts("test", 10, {"last_value": 1})
    assert "system" in prompts and prompts["system"]


def test_prompt_mentions_assumptions_and_safety():
    prompts = build_prompts("freeze hiring", 10, {"last_value": 10_000_000})
    system = prompts["system"]
    for token in ("alpha", "beta", "inflation", "cost_target", "JSON only", "lag_months", "mid next year"):
        assert token.lower() in system.lower()
