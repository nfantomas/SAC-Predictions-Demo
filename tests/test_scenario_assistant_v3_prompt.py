from llm.scenario_assistant_v3 import build_prompts


def test_prompt_template_formats_without_keyerror():
    prompts = build_prompts("test", 10, {"last_value": 1})
    assert "system" in prompts and prompts["system"]


def test_prompt_mentions_assumptions_and_safety():
    prompts = build_prompts("freeze hiring", 10, {"last_value": 10_000_000})
    system = prompts["system"]
    for token in ("alpha", "beta", "inflation", "cost_target", "JSON only", "lag_months", "mid next year"):
        assert token.lower() in system.lower()


def test_prompt_mentions_decimal_units_and_minimal_driver_rules():
    prompts = build_prompts("keep costs flat", 10, {"last_value": 10_000_000})
    system = prompts["system"].lower()
    for token in (
        "all percentages are decimals",
        "0.05 = 5%",
        "beta_multiplier: 1.05",
        "cost_target_pct: -0.10",
        "growth_delta_pp_per_year: -0.02",
        "minimal parameterization by driver",
        "driver=cost_target",
        "driver=fte",
        "driver=cost",
        "capacity/productivity intent default",
        "sick leave up",
        "utilization down",
        "productivity up",
        "self-consistency",
        "ten_year_multiplier_estimate",
    ):
        assert token in system
