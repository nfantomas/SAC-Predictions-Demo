import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from llm.intent_schema import ScenarioIntent


def test_intent_examples_validate():
    examples = json.loads(Path("tests/fixtures/intent_examples.json").read_text())
    assert examples
    for item in examples:
        ScenarioIntent.model_validate(item)


def test_rejects_missing_required_field():
    item = {
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
    with pytest.raises(ValidationError):
        ScenarioIntent.model_validate(item)


def test_rejects_invalid_date_format():
    item = {
        "schema_version": "intent_v1",
        "intent_type": "policy",
        "driver": "auto",
        "direction": "hold",
        "magnitude": {"type": "none", "value": None},
        "timing": {"start": "2028-13", "duration_months": 12, "ramp_months": 3},
        "constraints": [],
        "entities": {"regions": None, "population": "global"},
        "severity": "operational",
        "confidence": "high",
        "need_clarification": False,
        "clarifying_question": None,
    }
    with pytest.raises(ValidationError):
        ScenarioIntent.model_validate(item)


def test_rejects_extra_keys():
    item = {
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
        "extra_field": "nope",
    }
    with pytest.raises(ValidationError):
        ScenarioIntent.model_validate(item)
