from llm.anthropic_provider import _request_payload


def test_request_payload_includes_deterministic_controls():
    payload = _request_payload(
        system_prompt="s",
        user_prompt="u",
        model="m",
        max_tokens=4096,
        temperature=0.0,
        top_p=1.0,
    )
    assert payload["temperature"] == 0.0
    assert payload["top_p"] == 1.0
    assert payload["max_tokens"] == 4096
