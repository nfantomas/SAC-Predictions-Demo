from narrative.scenario_assistant_v3 import suggest_preset_v3


def test_default_freeze_when_no_match():
    out = suggest_preset_v3("")
    assert out["preset_id"] == "freeze_hiring"
    assert "summary" in out["rationale"]


def test_keyword_mapping_outsource():
    out = suggest_preset_v3("We should outsource roles to a cheaper region")
    assert out["preset_id"] == "outsource_120_uk_cz"


def test_keyword_mapping_inflation():
    out = suggest_preset_v3("Inflation is rising in country A and B; cap hiring")
    assert out["preset_id"] == "inflation_shock"
    assert out["rationale"]["assumptions"]
