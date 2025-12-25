import os

from config import load_env_file
from llm.anthropic_provider import DEFAULT_MODEL, generate_json, list_models
from llm.provider import LLMError


def main() -> int:
    load_env_file(".env", override=True)
    try:
        models = list_models()
    except LLMError as exc:
        reason = str(exc)
        if reason == "missing_llm_key":
            print("LLM DISABLED (missing_key)")
            return 0
        print(f"LLM ERROR ({reason})")
        return 1

    model = os.getenv("ANTHROPIC_MODEL", DEFAULT_MODEL)
    print(f"Models found: {len(models)}")
    print(f"Selected model: {model}")
    if model not in models:
        print("LLM ERROR (model_not_available)")
        print("Available models:", ", ".join(models[:10]))
        return 1

    try:
        generate_json(
            "Return JSON only.",
            "Return an object with {\"ok\": true}.",
            {"ok": "bool"},
        )
    except LLMError as exc:
        print(f"LLM ERROR ({exc})")
        return 1

    print(f"LLM OK (anthropic, model={model})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
