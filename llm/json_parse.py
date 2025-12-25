import json
import re
from typing import Any, Dict


def _strip_fences(raw_text: str) -> str:
    cleaned = raw_text.strip()
    cleaned = re.sub(r"^```(?:json)?\\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\\s*```$", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def _extract_json_object(text: str) -> str:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("invalid_json_fragment")
    return text[start : end + 1]


def _escape_newlines_in_strings(text: str) -> str:
    escaped = []
    in_string = False
    escaped_flag = False
    for ch in text:
        if ch == '"' and not escaped_flag:
            in_string = not in_string
        if ch == "\n" and in_string:
            escaped.append("\\n")
            escaped_flag = False
            continue
        escaped.append(ch)
        if ch == "\\" and not escaped_flag:
            escaped_flag = True
        else:
            escaped_flag = False
    return "".join(escaped)


def parse_llm_json(raw_text: str) -> Dict[str, Any]:
    cleaned = _strip_fences(raw_text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        fragment = _extract_json_object(cleaned)
        try:
            return json.loads(fragment)
        except json.JSONDecodeError:
            repaired = _escape_newlines_in_strings(fragment)
            return json.loads(repaired)


def sanitize_excerpt(raw_text: str, limit: int = 400) -> str:
    cleaned = raw_text.replace("\n", " ").strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[:limit] + "..."
