import json
from dataclasses import asdict
from datetime import date
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from config import load_config
from demo.refresh import refresh_from_sac
from pipeline.cache import CacheError, load_cache
from pipeline.forecast_runner import run_forecast
from pipeline.scenario_runner import run_scenarios
from scenarios.presets import PRESETS


DEFAULT_CACHE_PATH = "data/cache/sac_export.csv"


def _parse_iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"Invalid date format: {value}") from exc


def _filter_rows(rows: List[Dict[str, str]], start: Optional[str], end: Optional[str]) -> List[Dict[str, str]]:
    if not start and not end:
        return rows
    start_date = _parse_iso_date(start) if start else None
    end_date = _parse_iso_date(end) if end else None
    if start_date and end_date and start_date > end_date:
        raise ValueError("start must be <= end")
    filtered = []
    for row in rows:
        row_date = _parse_iso_date(row["date"])
        if start_date and row_date < start_date:
            continue
        if end_date and row_date > end_date:
            continue
        filtered.append(row)
    return filtered


def health_status(cache_path: str = DEFAULT_CACHE_PATH) -> Dict[str, Any]:
    config = load_config()
    status: Dict[str, Any] = {
        "tenant_url": config.tenant_url,
        "provider_id": None,
        "cache": {"status": "missing"},
    }
    status["provider_id"] = config.provider_id

    try:
        _, meta = load_cache(data_path=cache_path)
        status["cache"] = {
            "status": "ok",
            "meta": asdict(meta),
        }
    except CacheError as exc:
        status["cache"] = {"status": "missing", "error": str(exc)}
    return status


def get_timeseries(
    from_cache: bool = True,
    start: Optional[str] = None,
    end: Optional[str] = None,
    cache_path: str = DEFAULT_CACHE_PATH,
) -> Dict[str, Any]:
    if not from_cache:
        refresh_from_sac(cache_path)
    rows, meta = load_cache(data_path=cache_path)
    filtered = _filter_rows(rows, start, end)
    return {"rows": filtered, "meta": asdict(meta)}


def _load_csv(path: str) -> List[Dict[str, str]]:
    with open(path, "r", encoding="utf-8") as handle:
        lines = handle.read().strip().splitlines()
    if not lines:
        raise CacheError("Cache is missing or empty.")
    header = lines[0].split(",")
    rows = []
    for line in lines[1:]:
        values = line.split(",")
        rows.append(dict(zip(header, values)))
    return rows


def get_forecast(from_cache: bool = True) -> Dict[str, Any]:
    if not from_cache:
        run_forecast()
    rows = _load_csv("data/cache/forecast.csv")
    return {"rows": rows}


def get_scenarios(from_cache: bool = True, scenario: Optional[str] = None) -> Dict[str, Any]:
    if not from_cache:
        run_scenarios()
    rows = _load_csv("data/cache/scenarios.csv")
    if scenario:
        if scenario not in PRESETS:
            valid = sorted(PRESETS.keys())
            raise ValueError(f"Unknown scenario '{scenario}'. Valid: {', '.join(valid)}")
        rows = [row for row in rows if row.get("scenario") == scenario]
    return {"rows": rows}


def _tool_list() -> Dict[str, Any]:
    return {
        "tools": [
            {
                "name": "health",
                "description": "Return tenant URL, provider ID, and cache status.",
                "input_schema": {},
            },
            {
                "name": "get_timeseries",
                "description": "Return normalized timeseries from cache (or refresh on demand).",
                "input_schema": {
                    "from_cache": "bool (default true)",
                    "start": "YYYY-MM-DD (optional)",
                    "end": "YYYY-MM-DD (optional)",
                },
            },
            {
                "name": "get_forecast",
                "description": "Return baseline forecast from cache (or refresh on demand).",
                "input_schema": {
                    "from_cache": "bool (default true)",
                },
            },
            {
                "name": "get_scenarios",
                "description": "Return scenario series from cache (or refresh on demand).",
                "input_schema": {
                    "from_cache": "bool (default true)",
                    "scenario": "string (optional)",
                },
            },
        ]
    }


class MCPHandler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length == 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid JSON body") from exc

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/tools":
            self._send_json(200, _tool_list())
            return
        self._send_json(404, {"error": "not found"})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            payload = self._read_body()
            if path == "/health":
                self._send_json(200, health_status())
                return
            if path == "/get_timeseries":
                from_cache = bool(payload.get("from_cache", True))
                start = payload.get("start")
                end = payload.get("end")
                result = get_timeseries(from_cache=from_cache, start=start, end=end)
                self._send_json(200, result)
                return
            if path == "/get_forecast":
                from_cache = bool(payload.get("from_cache", True))
                result = get_forecast(from_cache=from_cache)
                self._send_json(200, result)
                return
            if path == "/get_scenarios":
                from_cache = bool(payload.get("from_cache", True))
                scenario = payload.get("scenario")
                result = get_scenarios(from_cache=from_cache, scenario=scenario)
                self._send_json(200, result)
                return
            if path == "/tools":
                self._send_json(200, _tool_list())
                return
        except (ValueError, CacheError) as exc:
            self._send_json(400, {"error": str(exc)})
            return
        except Exception as exc:
            self._send_json(500, {"error": str(exc)})
            return

        self._send_json(404, {"error": "not found"})


def run(host: str = "127.0.0.1", port: int = 8080) -> None:
    server = ThreadingHTTPServer((host, port), MCPHandler)
    print(f"MCP server listening on http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Minimal MCP server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    run(host=args.host, port=args.port)
