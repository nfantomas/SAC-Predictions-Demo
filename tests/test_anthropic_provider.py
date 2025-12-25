import json
from urllib import error

import pytest

from llm.anthropic_provider import generate_json, list_models
from llm.provider import LLMError


def test_missing_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    with pytest.raises(LLMError):
        generate_json("sys", "user", None)


def test_success_response(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "key")

    class DummyResp:
        def __init__(self):
            self.body = json.dumps({"content": [{"type": "text", "text": "{\"ok\": true}"}]})

        def read(self):
            return self.body.encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr("llm.anthropic_provider.request.urlopen", lambda *args, **kwargs: DummyResp())
    result = generate_json("sys", "user", None)
    assert result["ok"] is True


def test_models_list(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "key")

    class DummyResp:
        def read(self):
            return json.dumps({"data": [{"id": "claude-sonnet-4-20250514"}]}).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr("llm.anthropic_provider.request.urlopen", lambda *args, **kwargs: DummyResp())
    models = list_models()
    assert "claude-sonnet-4-20250514" in models


def test_retry_on_429(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "key")
    calls = {"count": 0}

    def fake_urlopen(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise error.HTTPError("url", 429, "rate", {}, None)

        class DummyResp:
            def read(self):
                return json.dumps({"content": [{"type": "text", "text": "{\"ok\": true}"}]}).encode("utf-8")

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        return DummyResp()

    monkeypatch.setattr("llm.anthropic_provider.request.urlopen", fake_urlopen)
    result = generate_json("sys", "user", None)
    assert result["ok"] is True


def test_invalid_json_fallback(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "key")

    class DummyResp:
        def read(self):
            return json.dumps({"content": [{"type": "text", "text": "not json"}]}).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr("llm.anthropic_provider.request.urlopen", lambda *args, **kwargs: DummyResp())
    with pytest.raises(LLMError):
        generate_json("sys", "user", None)


def test_timeout_fallback(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "key")

    def fake_urlopen(*args, **kwargs):
        raise error.URLError("timeout")

    monkeypatch.setattr("llm.anthropic_provider.request.urlopen", fake_urlopen)
    with pytest.raises(LLMError):
        generate_json("sys", "user", None)
