import pandas as pd
import pytest

from narrative.generator import NarrativeError, generate_narrative, summarize_series


def test_template_schema_deterministic():
    df = pd.DataFrame(
        {"date": ["2020-01-01", "2020-02-01"], "value": [100.0, 101.0]}
    )
    stats = summarize_series(df)
    out = generate_narrative(stats, {}, "", use_llm=False)
    assert out["mode"] == "template"
    assert out["title"]
    assert out["summary"]
    assert isinstance(out["bullets"], list)
    assert out["assumptions"]


def test_llm_missing_key_fallback(monkeypatch):
    df = pd.DataFrame(
        {"date": ["2020-01-01", "2020-02-01"], "value": [100.0, 101.0]}
    )
    stats = summarize_series(df)
    monkeypatch.delenv("NARRATIVE_LLM_KEY", raising=False)
    out = generate_narrative(stats, {}, "", use_llm=True)
    assert out["mode"] == "template"
    assert out["reason"] == "missing_llm_key"


def test_summarize_rejects_empty():
    with pytest.raises(NarrativeError):
        summarize_series(pd.DataFrame(columns=["date", "value"]))
