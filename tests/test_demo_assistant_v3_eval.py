from demo.assistant_v3_eval import _apply_eval_llm_limits


def test_apply_eval_llm_limits_uses_minimums(monkeypatch):
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "600")
    monkeypatch.setenv("LLM_MAX_RETRIES", "2")
    monkeypatch.setenv("LLM_MAX_TOKENS", "2048")
    timeout, retries, tokens = _apply_eval_llm_limits(None, None, None)
    assert timeout == 900
    assert retries == 4
    assert tokens == 4096


def test_apply_eval_llm_limits_respects_explicit_overrides(monkeypatch):
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "600")
    monkeypatch.setenv("LLM_MAX_RETRIES", "2")
    monkeypatch.setenv("LLM_MAX_TOKENS", "2048")
    timeout, retries, tokens = _apply_eval_llm_limits(1200, 6, 8192)
    assert timeout == 1200
    assert retries == 6
    assert tokens == 8192
