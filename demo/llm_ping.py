from __future__ import annotations

from llm.anthropic_provider import generate_json
from llm.provider import LLMError


def main() -> int:
    system_prompt = "You are a JSON-only responder."
    user_prompt = 'Return exactly this JSON object: {"ping": "pong"}. No extra keys.'
    schema_hint = {"ping": "string"}

    try:
        result = generate_json(system_prompt, user_prompt, schema_hint=schema_hint)
    except LLMError as exc:
        print(f"LLM ERROR ({exc})")
        return 1

    if result.get("ping") != "pong":
        print("LLM ERROR (unexpected_response)")
        print(f"Response: {result}")
        return 1

    print("LLM OK (ping)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
