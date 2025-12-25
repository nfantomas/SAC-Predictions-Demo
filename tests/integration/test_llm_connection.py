import os

import pytest

from llm.anthropic_provider import generate_json


@pytest.mark.llm
def test_llm_ping_expected_answer():
    if os.getenv("RUN_LLM_TESTS") != "1":
        pytest.skip("RUN_LLM_TESTS!=1")
    if not os.getenv("ANTHROPIC_API_KEY"):
        pytest.skip("missing ANTHROPIC_API_KEY")

    result = generate_json(
        "You are a JSON-only responder.",
        'Return exactly this JSON object: {"ping": "pong"}. No extra keys.',
        schema_hint={"ping": "string"},
    )
    assert result.get("ping") == "pong"
