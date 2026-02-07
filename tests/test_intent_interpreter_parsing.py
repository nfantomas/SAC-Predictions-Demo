from __future__ import annotations

import json

from llm.intent_interpreter import interpret_intent


def _sample_intent() -> dict:
    return {
        "schema_version": "intent_v1",
        "intent_type": "policy",
        "driver": "auto",
        "direction": "hold",
        "magnitude": {"type": "none", "value": None},
        "timing": {"start": "2028-01", "duration_months": 12, "ramp_months": 3},
        "constraints": [],
        "entities": {"regions": None, "population": "global"},
        "severity": "operational",
        "confidence": "high",
        "need_clarification": False,
        "clarifying_question": None,
    }


def test_interpreter_parses_valid_json(monkeypatch):
    def fake_call(system, user):
        return _sample_intent()

    monkeypatch.setattr("llm.intent_interpreter._call_llm", fake_call)
    result = interpret_intent("freeze hiring", {})
    assert result["intent"]["schema_version"] == "intent_v1"
    assert result["repaired"] is False


def test_interpreter_parses_fenced_json(monkeypatch):
    payload = json.dumps(_sample_intent())

    def fake_call(system, user):
        return f"```json\n{payload}\n```"

    monkeypatch.setattr("llm.intent_interpreter._call_llm", fake_call)
    result = interpret_intent("freeze hiring", {})
    assert result["intent"]["schema_version"] == "intent_v1"


def test_interpreter_repair_retry(monkeypatch):
    calls = iter(["not json", _sample_intent()])

    def fake_call(system, user):
        return next(calls)

    monkeypatch.setattr("llm.intent_interpreter._call_llm", fake_call)
    result = interpret_intent("freeze hiring", {})
    assert result["intent"]["schema_version"] == "intent_v1"
    assert result["repaired"] is True


def test_interpreter_partial_json_requires_repair(monkeypatch):
    partial = "{ \"schema_version\": \"intent_v1\""
    calls = iter([partial, _sample_intent()])

    def fake_call(system, user):
        return next(calls)

    monkeypatch.setattr("llm.intent_interpreter._call_llm", fake_call)
    result = interpret_intent("freeze hiring", {})
    assert result["intent"]["schema_version"] == "intent_v1"
    assert result["repaired"] is True


def test_interpreter_fallback(monkeypatch):
    calls = iter(["not json", "still bad"])

    def fake_call(system, user):
        return next(calls)

    monkeypatch.setattr("llm.intent_interpreter._call_llm", fake_call)
    result = interpret_intent("???", {})
    assert result["intent"]["need_clarification"] is True
    assert result.get("fallback") is True


def test_interpreter_heuristics_for_no_layoffs_cost_target(monkeypatch):
    weak = _sample_intent()
    weak["intent_type"] = "constraint"
    weak["driver"] = "auto"
    weak["magnitude"] = {"type": "none", "value": None}
    weak["constraints"] = []

    def fake_call(system, user):
        return weak

    monkeypatch.setattr("llm.intent_interpreter._call_llm", fake_call)
    prompt = "If we set a constraint no layoffs, how do we achieve a 10% cost reduction?"
    result = interpret_intent(prompt, {})
    intent = result["intent"]
    assert intent["intent_type"] == "target"
    assert intent["driver"] == "cost_target"
    assert intent["magnitude"]["value"] == -0.1
    assert "no_layoffs" in intent["constraints"]
