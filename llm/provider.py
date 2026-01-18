from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from config import load_env_file


class LLMError(Exception):
    pass


def _select_provider() -> str:
    load_env_file(".env", override=False)
    provider = (os.getenv("LLM_PROVIDER") or "").strip().lower()
    if provider == "anthropic":
        return provider
    # Only Anthropic is supported.
    if (os.getenv("ANTHROPIC_API_KEY") or "").strip():
        return "anthropic"
    return "anthropic"


def provider_name() -> str:
    return _select_provider()


def has_llm_key() -> bool:
    provider = _select_provider()
    return bool((os.getenv("ANTHROPIC_API_KEY") or "").strip())


def default_model() -> str:
    provider = _select_provider()
    from llm.anthropic_provider import DEFAULT_MODEL

    return DEFAULT_MODEL


def model_name() -> str:
    provider = _select_provider()
    return (os.getenv("ANTHROPIC_MODEL") or default_model()).strip() or default_model()


def list_models() -> List[str]:
    provider = _select_provider()
    from llm.anthropic_provider import list_models as impl

    return impl()


def generate_json(
    system_prompt: str,
    user_prompt: str,
    schema_hint: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    provider = _select_provider()
    from llm.anthropic_provider import generate_json as impl

    return impl(system_prompt, user_prompt, schema_hint=schema_hint)


def get_last_raw_text() -> str:
    provider = _select_provider()
    from llm.anthropic_provider import get_last_raw_text as impl

    return impl()


def get_last_raw_excerpt() -> str:
    provider = _select_provider()
    from llm.anthropic_provider import get_last_raw_excerpt as impl

    return impl()


def get_last_usage() -> Dict[str, Any]:
    provider = _select_provider()
    from llm.anthropic_provider import get_last_usage as impl

    return impl()
