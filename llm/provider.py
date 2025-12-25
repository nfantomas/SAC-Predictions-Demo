from __future__ import annotations

from typing import Any, Dict, Optional


class LLMError(Exception):
    pass


def generate_json(system_prompt: str, user_prompt: str, schema_hint: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    raise NotImplementedError("Provider not configured.")
