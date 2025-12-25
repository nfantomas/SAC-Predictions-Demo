from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional
from urllib import error, request

from config import load_env_file
from llm.json_parse import parse_llm_json, sanitize_excerpt
from llm.provider import LLMError


DEFAULT_MODEL = "claude-opus-4-20250514"
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
    load_env_file(".env", override=True)


def _request_payload(system_prompt: str, user_prompt: str, model: str, max_tokens: int) -> Dict[str, Any]:
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system_prompt,
        "messages": [
            {
                "role": "user",
                "content": [{"type": "text", "text": user_prompt}],
            }
        ],
    }
    stop_env = os.getenv("LLM_STOP_SEQUENCES", "")
    stop_sequences = [item.strip() for item in stop_env.split(",") if item.strip()]
    if stop_sequences:
        payload["stop_sequences"] = stop_sequences
    return payload


def list_models() -> List[str]:
    _ensure_env_loaded()
    api_key = (os.getenv("ANTHROPIC_API_KEY") or "").strip().strip('"').strip("'")
    if not api_key:
        raise LLMError("missing_llm_key")

    timeout = int(os.getenv("LLM_TIMEOUT_SECONDS", "30"))
    base = os.getenv("ANTHROPIC_API_BASE", "https://api.anthropic.com").rstrip("/")
    url = f"{base}/v1/models"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }
    beta = os.getenv("ANTHROPIC_BETA")
    if beta:
        headers["anthropic-beta"] = beta

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


def generate_json(system_prompt: str, user_prompt: str, schema_hint: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    _ensure_env_loaded()
    api_key = (os.getenv("ANTHROPIC_API_KEY") or "").strip().strip('"').strip("'")
    if not api_key:
        raise LLMError("missing_llm_key")

    model = os.getenv("ANTHROPIC_MODEL", DEFAULT_MODEL)
    timeout = int(os.getenv("LLM_TIMEOUT_SECONDS", "30"))
    max_retries = int(os.getenv("LLM_MAX_RETRIES", "2"))
    max_tokens = int(os.getenv("LLM_MAX_TOKENS", "2048"))
    base = os.getenv("ANTHROPIC_API_BASE", "https://api.anthropic.com").rstrip("/")

    payload = _request_payload(system_prompt, user_prompt, model, max_tokens)
    if schema_hint:
        payload["system"] = f"{system_prompt}\nReturn JSON matching this schema: {schema_hint}"

    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }
    beta = os.getenv("ANTHROPIC_BETA")
    if beta:
        headers["anthropic-beta"] = beta
    base = os.getenv("ANTHROPIC_API_BASE", "https://api.anthropic.com").rstrip("/")
    url = f"{base}/v1/messages"

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

        content = parsed.get("content") or []
        text = ""
        for block in content:
            if block.get("type") == "text":
                text += block.get("text", "")
        if not text:
            raise LLMError("invalid_llm_output")
        global _LAST_RAW_TEXT
        global _LAST_RAW_EXCERPT
        _LAST_RAW_TEXT = text
        _LAST_RAW_EXCERPT = sanitize_excerpt(text)

        try:
            return parse_llm_json(text)
        except ValueError as exc:
            raise LLMError("invalid_llm_output") from exc

    raise LLMError("llm_unknown")
