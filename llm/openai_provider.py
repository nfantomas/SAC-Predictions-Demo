from __future__ import annotations

import json
import os
import socket
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib import error, request

from config import load_env_file
from llm.json_parse import parse_llm_json, sanitize_excerpt
from llm.provider import LLMError


DEFAULT_MODEL = "gpt-5.2"
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


def _resolve_api_key() -> str:
    _ensure_env_loaded()
    key = (os.getenv("OPENAI_API_KEY") or "").strip().strip('"').strip("'")
    if (not key) or key.lower().startswith("your_") or "<" in key:
        load_env_file(".env", override=True)
        key = (os.getenv("OPENAI_API_KEY") or "").strip().strip('"').strip("'")
    return key


def _resolve_base_url() -> str:
    _ensure_env_loaded()
    base = (os.getenv("OPENAI_API_BASE") or "https://api.openai.com/v1").strip()
    for suffix in ("/chat/completions", "/chat/completions/", "/models", "/models/"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break
    return base.rstrip("/")


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


def _extract_error_message(body: str) -> str:
    if not body:
        return ""
    try:
        parsed = json.loads(body)
    except Exception:
        return body[:300]
    err = parsed.get("error", {})
    if isinstance(err, dict):
        msg = err.get("message") or ""
        code = err.get("code") or ""
        tpe = err.get("type") or ""
        parts = [str(x) for x in (msg, code, tpe) if x]
        return " | ".join(parts)
    return body[:300]


def _post_json(url: str, payload: Dict[str, Any], headers: Dict[str, str], timeout: int, max_retries: int) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    last_http_400_detail = ""
    for attempt in range(max_retries + 1):
        try:
            req = request.Request(url, data=data, headers=headers, method="POST")
            with request.urlopen(req, timeout=timeout) as resp:
                parsed = json.loads(resp.read().decode("utf-8"))
                return parsed
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
            if status == 400:
                last_http_400_detail = _extract_error_message(body)
                break
            raise LLMError(f"llm_http_{status}") from exc
        except error.URLError as exc:
            reason = _classify_url_error(exc)
            if _is_retryable_network_reason(reason) and attempt < max_retries:
                time.sleep(1.0 * (attempt + 1))
                continue
            raise LLMError(reason) from exc
    raise LLMError(f"llm_http_400:{last_http_400_detail}" if last_http_400_detail else "llm_http_400")


def list_models() -> List[str]:
    api_key = _resolve_api_key()
    if not api_key:
        raise LLMError("missing_llm_key")

    timeout = int(os.getenv("LLM_TIMEOUT_SECONDS", "600"))
    max_retries = int(os.getenv("LLM_MAX_RETRIES", "3"))
    base = _resolve_base_url()
    url = f"{base}/models"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    for attempt in range(max_retries + 1):
        try:
            req = request.Request(url, headers=headers, method="GET")
            with request.urlopen(req, timeout=timeout) as resp:
                parsed = json.loads(resp.read().decode("utf-8"))
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

    models: List[str] = []
    for entry in parsed.get("data", []):
        model_id = entry.get("id")
        if model_id:
            models.append(model_id)
    return models


def generate_json(system_prompt: str, user_prompt: str, schema_hint: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    api_key = _resolve_api_key()
    if not api_key:
        raise LLMError("missing_llm_key")

    model = (os.getenv("OPENAI_MODEL") or DEFAULT_MODEL).strip() or DEFAULT_MODEL
    timeout = int(os.getenv("LLM_TIMEOUT_SECONDS", "600"))
    max_retries = int(os.getenv("LLM_MAX_RETRIES", "3"))
    max_tokens = max(int(os.getenv("LLM_MAX_TOKENS", "4096")), 4096)
    temperature = float(os.getenv("LLM_TEMPERATURE", "0"))
    top_p = float(os.getenv("LLM_TOP_P", "1"))

    if schema_hint:
        system_prompt = f"{system_prompt}\nReturn JSON matching this schema: {schema_hint}"

    responses_payload: Dict[str, Any] = {
        "model": model,
        "temperature": temperature,
        "top_p": top_p,
        "max_output_tokens": max_tokens,
        "input": [
            {
                "role": "system",
                "content": [{"type": "input_text", "text": system_prompt}],
            },
            {
                "role": "user",
                "content": [{"type": "input_text", "text": user_prompt}],
            },
        ],
    }
    chat_payload: Dict[str, Any] = {
        "model": model,
        "temperature": temperature,
        "top_p": top_p,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    base = _resolve_base_url()
    attempts: List[Tuple[str, Dict[str, Any]]] = [
        (f"{base}/responses", responses_payload),
        (f"{base}/chat/completions", chat_payload),
    ]

    last_error = "llm_unknown"
    for url, payload in attempts:
        try:
            parsed = _post_json(url, payload, headers, timeout, max_retries)
            global _LAST_USAGE
            _LAST_USAGE = parsed.get("usage", {}) or {}
        except LLMError as exc:
            last_error = str(exc)
            # Fallback to alternate endpoint for bad-request shape mismatches.
            if str(exc).startswith("llm_http_400"):
                continue
            raise

        text = ""
        if "output_text" in parsed and isinstance(parsed.get("output_text"), str):
            text = parsed["output_text"]
        if not text:
            output = parsed.get("output") or []
            if output and isinstance(output, list):
                for item in output:
                    for content in item.get("content", []) if isinstance(item, dict) else []:
                        if content.get("type") in ("output_text", "text"):
                            text += content.get("text", "")
        if not text:
            choices = parsed.get("choices") or []
            msg = choices[0].get("message", {}) if choices else {}
            text = msg.get("content", "") if isinstance(msg, dict) else ""

        if not text:
            last_error = "invalid_llm_output"
            continue

        global _LAST_RAW_TEXT
        global _LAST_RAW_EXCERPT
        _LAST_RAW_TEXT = text
        _LAST_RAW_EXCERPT = sanitize_excerpt(text)

        try:
            return parse_llm_json(text)
        except ValueError:
            raise LLMError("invalid_llm_output")

    raise LLMError(last_error)
