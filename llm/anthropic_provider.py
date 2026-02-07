from __future__ import annotations

import json
import os
import socket
import time
from typing import Any, Dict, List, Optional
from urllib import error, request

from config import load_env_file
from llm.json_parse import parse_llm_json, sanitize_excerpt
from llm.provider import LLMError


# Default to a lightweight model to reduce latency; override via ANTHROPIC_MODEL.
DEFAULT_MODEL = "claude-3-haiku-20240307"
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


def _clean_api_key(key: str) -> str:
    # Anthropic expects ASCII header values; strip quotes, whitespace, ellipsis, and non-ASCII.
    key = key.strip().strip('"').strip("'")
    key = key.replace("\u2026", "...")  # common when pasting a masked key
    key = key.encode("ascii", "ignore").decode("ascii")
    return key


def _resolve_api_key() -> str:
    _ensure_env_loaded()
    key = _clean_api_key(os.getenv("ANTHROPIC_API_KEY") or "")
    if (not key) or key.lower().startswith("your_") or "<" in key:
        load_env_file(".env", override=True)
        key = _clean_api_key(os.getenv("ANTHROPIC_API_KEY") or "")
    return key


def _resolve_base_url() -> str:
    _ensure_env_loaded()
    base = (os.getenv("ANTHROPIC_API_BASE") or "https://api.anthropic.com").strip()
    for suffix in ("/v1/messages", "/v1/messages/", "/v1/", "/v1"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break
    return base.rstrip("/")


def _request_payload(
    system_prompt: str,
    user_prompt: str,
    model: str,
    max_tokens: int,
    temperature: float,
    top_p: float,
) -> Dict[str, Any]:
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "top_p": top_p,
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


def _classify_url_error(exc: error.URLError) -> str:
    reason = getattr(exc, "reason", exc)
    if isinstance(reason, socket.gaierror):
        return "llm_dns_error"
    if isinstance(reason, (socket.timeout, TimeoutError)):
        return "llm_timeout"

    msg = str(reason).lower()
    if "nodename nor servname" in msg or "name or service not known" in msg:
        return "llm_dns_error"
    if "temporary failure in name resolution" in msg:
        return "llm_dns_error"
    if "timed out" in msg:
        return "llm_timeout"
    if "connection refused" in msg:
        return "llm_connection_refused"
    if "certificate verify failed" in msg or "ssl" in msg:
        return "llm_ssl_error"
    return "llm_network_error"


def _is_retryable_network_reason(reason: str) -> bool:
    return reason in ("llm_timeout", "llm_network_error", "llm_dns_error")


def list_models() -> List[str]:
    api_key = _resolve_api_key()
    if not api_key:
        raise LLMError("missing_llm_key")

    timeout = int(os.getenv("LLM_TIMEOUT_SECONDS", "600"))
    base = _resolve_base_url()
    url = f"{base}/v1/models"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }
    beta = os.getenv("ANTHROPIC_BETA")
    if beta:
        headers["anthropic-beta"] = beta

    max_retries = int(os.getenv("LLM_MAX_RETRIES", "3"))
    for attempt in range(max_retries + 1):
        try:
            req = request.Request(url, headers=headers, method="GET")
            with request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8")
                parsed = json.loads(body)
            break
        except error.HTTPError as exc:
            status = exc.code
            if status in (429, 500, 502, 503, 504) and attempt < max_retries:
                time.sleep(1.0 * (attempt + 1))
                continue
            if status == 401:
                raise LLMError("llm_http_401_invalid_key") from exc
            raise LLMError(f"llm_http_{status}") from exc
        except error.URLError as exc:
            reason = _classify_url_error(exc)
            if _is_retryable_network_reason(reason) and attempt < max_retries:
                time.sleep(1.0 * (attempt + 1))
                continue
            raise LLMError(reason) from exc

    models = []
    for entry in parsed.get("data", []):
        model_id = entry.get("id")
        if model_id:
            models.append(model_id)
    return models


def generate_json(system_prompt: str, user_prompt: str, schema_hint: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    api_key = _resolve_api_key()
    if not api_key:
        raise LLMError("missing_llm_key")

    model = (os.getenv("ANTHROPIC_MODEL") or DEFAULT_MODEL).strip() or DEFAULT_MODEL
    timeout = int(os.getenv("LLM_TIMEOUT_SECONDS", "600"))
    max_retries = int(os.getenv("LLM_MAX_RETRIES", "3"))
    max_tokens = max(int(os.getenv("LLM_MAX_TOKENS", "4096")), 4096)
    temperature = float(os.getenv("LLM_TEMPERATURE", "0"))
    top_p = float(os.getenv("LLM_TOP_P", "1"))
    payload = _request_payload(system_prompt, user_prompt, model, max_tokens, temperature, top_p)
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
    base = _resolve_base_url()
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
            reason = _classify_url_error(exc)
            if _is_retryable_network_reason(reason) and attempt < max_retries:
                time.sleep(1.0 * (attempt + 1))
                continue
            raise LLMError(reason) from exc

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
        except ValueError:
            # Preserve raw text for debugging.
            raise LLMError("invalid_llm_output")

    raise LLMError("llm_unknown")
