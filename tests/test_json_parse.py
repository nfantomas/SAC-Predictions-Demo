import pytest

from llm.json_parse import parse_llm_json


def test_parse_raw_json():
    raw = '{"ok": true, "value": 1}'
    parsed = parse_llm_json(raw)
    assert parsed["ok"] is True
    assert parsed["value"] == 1


def test_parse_fenced_json():
    raw = '```json\n{\n  "ok": true\n}\n```'
    parsed = parse_llm_json(raw)
    assert parsed["ok"] is True


def test_parse_json_with_commentary():
    raw = 'Note:\n{\n  "ok": true\n}\nThanks'
    parsed = parse_llm_json(raw)
    assert parsed["ok"] is True


def test_truncated_json_raises():
    raw = '{\n  "ok": true\n'
    with pytest.raises(ValueError):
        parse_llm_json(raw)


def test_parse_json_with_newline_in_string():
    raw = '{\n  "summary": "Line one\nLine two"\n}'
    parsed = parse_llm_json(raw)
    assert "Line one" in parsed["summary"]
