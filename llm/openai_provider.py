from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional
from urllib import error, request

from config import load_env_file
from llm.json_parse import parse_llm_json, sanitize_excerpt
from llm.provider import LLMError


DEFAULT_MODEL = "gpt-4o-mini"
_LAST_RAW_TEXT = ""
_LAST_RAW_EXCERPT = ""
_LAST_USAGE = {}


def get_last_raw_text() -> str:
    return _LAST_RAW_TEXT


def get_last_raw_excerpt() -> str:
    return _LAST_RAW_EXCERPT


def get_last_usage() -> Dict[str, Any]:
    return _LAST_USAGE


def _ensure_env_loaded() -> None:
    load_env_file(".env", override=False)


def _build_headers(api_key: str) -> Dict[str, str]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    org_id = (os.getenv("OPENAI_ORG_ID") or "").strip()
    if org_id:
        headers["OpenAI-Organization"] = org_id
    project_id = (os.getenv("OPENAI_PROJECT") or "").strip()
    if project_id:
        headers["OpenAI-Project"] = project_id
    return headers


def _request_payload(system_prompt: str, user_prompt: str, model: str, max_tokens: int) -> Dict[str, Any]:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0,
        "max_tokens": max_tokens,
    }
    stop_env = os.getenv("LLM_STOP_SEQUENCES", "")
    stop_sequences = [item.strip() for item in stop_env.split(",") if item.strip()]
    if stop_sequences:
        payload["stop"] = stop_sequences
    return payload


def list_models() -> List[str]:
    _ensure_env_loaded()
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip().strip('"').strip("'")
    if not api_key:
        raise LLMError("missing_llm_key")

    timeout = int(os.getenv("LLM_TIMEOUT_SECONDS", "30"))
    base = os.getenv("OPENAI_API_BASE", "https://api.openai.com").rstrip("/")
    url = f"{base}/v1/models"
    headers = _build_headers(api_key)

    try:
        req = request.Request(url, headers=headers, method="GET")
        with request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            parsed = json.loads(body)
    except error.HTTPError as exc:
        status = exc.code
        if status == 401:
            raise LLMError("llm_http_401_invalid_key") from exc
        raise LLMError(f"llm_http_{status}") from exc
    except error.URLError as exc:
        raise LLMError("llm_timeout") from exc

    models = []
    for entry in parsed.get("data", []):
        model_id = entry.get("id")
        if model_id:
            models.append(model_id)
    return models


def generate_json(
    system_prompt: str,
    user_prompt: str,
    schema_hint: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    _ensure_env_loaded()
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip().strip('"').strip("'")
    if not api_key:
        raise LLMError("missing_llm_key")

    model = (os.getenv("OPENAI_MODEL") or DEFAULT_MODEL).strip() or DEFAULT_MODEL
    timeout = int(os.getenv("LLM_TIMEOUT_SECONDS", "30"))
    max_retries = int(os.getenv("LLM_MAX_RETRIES", "2"))
    max_tokens = int(os.getenv("LLM_MAX_TOKENS", "2048"))
    base = os.getenv("OPENAI_API_BASE", "https://api.openai.com").rstrip("/")
    url = f"{base}/v1/chat/completions"

    if schema_hint:
        system_prompt = f"{system_prompt}\nReturn JSON matching this schema: {schema_hint}"
    payload = _request_payload(system_prompt, user_prompt, model, max_tokens)
    data = json.dumps(payload).encode("utf-8")
    headers = _build_headers(api_key)

    for attempt in range(max_retries + 1):
        try:
            req = request.Request(url, data=data, headers=headers, method="POST")
            with request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8")
                parsed = json.loads(body)
                global _LAST_USAGE
                _LAST_USAGE = parsed.get("usage", {}) or {}
        except error.HTTPError as exc:
            status = exc.code
            body = ""
            try:
                body = exc.read().decode("utf-8")
            except Exception:
                body = ""
            if status in (429, 500, 502, 503, 504) and attempt < max_retries:
                time.sleep(1.0 * (attempt + 1))
                continue
            if status == 401:
                raise LLMError("llm_http_401_invalid_key") from exc
            raise LLMError(f"llm_http_{status}") from exc
        except error.URLError as exc:
            if attempt < max_retries:
                time.sleep(1.0 * (attempt + 1))
                continue
            raise LLMError("llm_timeout") from exc

        choices = parsed.get("choices", [])
        content = ""
        if choices:
            message = choices[0].get("message", {})
            content = message.get("content") or ""
        if not content:
            raise LLMError("invalid_llm_output")
        global _LAST_RAW_TEXT
        global _LAST_RAW_EXCERPT
        _LAST_RAW_TEXT = content
        _LAST_RAW_EXCERPT = sanitize_excerpt(content)

        try:
            return parse_llm_json(content)
        except ValueError as exc:
            raise LLMError("invalid_llm_output") from exc

    raise LLMError("llm_unknown")
