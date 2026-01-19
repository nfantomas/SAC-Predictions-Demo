import json

import pytest

from llm.validate_suggestion import SuggestionValidationError
from ui.assistant_v3_pipeline import parse_suggestion


def test_parse_suggestion_rejects_markdown_fences():
    fenced = """```json
{"suggested_driver": "cost", "params": {"driver": "cost"}}
```"""
    with pytest.raises(SuggestionValidationError):
        parse_suggestion(fenced)


def test_parse_suggestion_parses_clean_json():
    payload = {"suggested_driver": "cost", "params": {"driver": "cost"}}
    raw = json.dumps(payload)
    assert parse_suggestion(raw) == payload
