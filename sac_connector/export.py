import json
import time
from dataclasses import dataclass
from datetime import date, datetime
from typing import Dict, Iterable, List, Optional, Sequence
from urllib import error, parse, request

from sac_connector.auth import AuthError, TokenInfo, request_token
from config import Config


class ExportError(Exception):
    pass


class ExportHttpError(Exception):
    def __init__(self, status: int, body: str):
        super().__init__(f"HTTP {status}")
        self.status = status
        self.body = body


@dataclass(frozen=True)
class ExportRequest:
    url: str
    params: Dict[str, str]
    headers: Dict[str, str]


def _request_json(url: str, headers: Dict[str, str], timeout: int) -> Dict:
    req = request.Request(url, headers=headers, method="GET")
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            payload = resp.read().decode("utf-8")
    except error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8")
        except Exception:
            body = ""
        raise ExportHttpError(exc.code, body) from exc
    except error.URLError as exc:
        raise ExportError(f"Export failed: {exc.reason}") from exc

    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ExportError("Export failed: Invalid JSON in response.") from exc


def _retry_backoff(attempt: int, base_seconds: float = 1.0, cap_seconds: float = 10.0) -> float:
    return min(cap_seconds, base_seconds * (2 ** (attempt - 1)))


def _should_retry(status: int) -> bool:
    return status == 429 or status >= 500


def request_json_with_retry(
    url: str,
    headers: Dict[str, str],
    timeout: int = 30,
    max_attempts: int = 5,
) -> Dict:
    for attempt in range(1, max_attempts + 1):
        try:
            return _request_json(url, headers=headers, timeout=timeout)
        except ExportHttpError as exc:
            if not _should_retry(exc.status) or attempt == max_attempts:
                message = exc.body.strip() or f"HTTP {exc.status}"
                raise ExportError(f"Export failed ({exc.status}): {message}") from exc
            sleep_seconds = _retry_backoff(attempt)
            time.sleep(sleep_seconds)
    raise ExportError("Export failed: retries exhausted.")


def _extract_rows(payload: object) -> List[Dict]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("data", "value", "rows"):
            if key in payload and isinstance(payload[key], list):
                return payload[key]
    raise ExportError("Export failed: response does not contain row data.")


def _next_url(payload: Dict, current_url: str) -> Optional[str]:
    if "@odata.nextLink" in payload:
        return _resolve_next(payload["@odata.nextLink"], current_url)
    if "nextLink" in payload:
        return _resolve_next(payload["nextLink"], current_url)
    if "next" in payload:
        return _resolve_next(payload["next"], current_url)
    links = payload.get("links")
    if isinstance(links, dict) and "next" in links:
        return _resolve_next(links["next"], current_url)
    if "continuationToken" in payload:
        token = payload["continuationToken"]
        return _append_query(current_url, {"continuationToken": token})
    if "skipToken" in payload:
        token = payload["skipToken"]
        return _append_query(current_url, {"$skiptoken": token})
    return None


def _resolve_next(next_link: str, current_url: str) -> str:
    return parse.urljoin(current_url, next_link)


def _append_query(url: str, params: Dict[str, str]) -> str:
    parsed = parse.urlparse(url)
    query = dict(parse.parse_qsl(parsed.query))
    query.update(params)
    new_query = parse.urlencode(query)
    return parse.urlunparse(parsed._replace(query=new_query))


def _normalize_date(value: object, grain: str) -> str:
    if value is None:
        raise ValueError("date is required")
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return value.isoformat()

    text = str(value).strip()
    if not text:
        raise ValueError("date is required")

    if "T" in text:
        text = text.split("T", 1)[0]

    if len(text) == 7 and text[4] == "-":
        year, month = text.split("-")
        return date(int(year), int(month), 1).isoformat()

    if len(text) == 4 and text.isdigit():
        return date(int(text), 1, 1).isoformat()

    if "Q" in text:
        text = text.replace("-", "")
        year = int(text[:4])
        quarter = int(text[-1])
        month = (quarter - 1) * 3 + 1
        return date(year, month, 1).isoformat()

    try:
        return datetime.fromisoformat(text).date().isoformat()
    except ValueError as exc:
        raise ValueError(f"Unrecognized date format: {value}") from exc


def normalize_rows(
    rows: Sequence[Dict],
    date_field: str,
    value_field: str,
    dim_fields: Iterable[str],
    grain: str = "month",
) -> List[Dict]:
    normalized = []
    for row in rows:
        if date_field not in row or value_field not in row:
            raise ExportError("Normalization failed: missing date or value field.")
        normalized_row = {
            "date": _normalize_date(row[date_field], grain),
            "value": float(row[value_field]),
        }
        for dim in dim_fields:
            normalized_row[f"dim_{dim}"] = "" if row.get(dim) is None else str(row.get(dim))
        normalized.append(normalized_row)
    return normalized


def _build_headers(token_info: TokenInfo) -> Dict[str, str]:
    return {
        "Authorization": f"{token_info.token_type} {token_info.access_token}",
        "Accept": "application/json",
        "x-sap-sac-custom-auth": "true",
    }


def build_export_request(
    url: str,
    params: Optional[Dict[str, str]],
    token_info: TokenInfo,
) -> ExportRequest:
    full_url = _append_query(url, params or {})
    return ExportRequest(url=full_url, params=params or {}, headers=_build_headers(token_info))


def export_all(
    config: Config,
    export_url: str,
    params: Optional[Dict[str, str]] = None,
    timeout: int = 30,
    max_attempts: int = 5,
) -> List[Dict]:
    try:
        token_info = request_token(config)
    except AuthError as exc:
        raise ExportError(str(exc)) from exc

    export_request = build_export_request(export_url, params, token_info)
    rows: List[Dict] = []
    next_url: Optional[str] = export_request.url

    while next_url:
        payload = request_json_with_retry(
            next_url,
            headers=export_request.headers,
            timeout=timeout,
            max_attempts=max_attempts,
        )
        page_rows = _extract_rows(payload)
        rows.extend(page_rows)
        next_url = _next_url(payload, next_url)

    return rows
