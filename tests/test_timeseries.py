from datetime import datetime, timezone
from types import SimpleNamespace
from urllib import parse

import pandas as pd

from sac_connector import export as export_module
from sac_connector.timeseries import fetch_timeseries


def _mock_token():
    return export_module.TokenInfo(
        access_token="token",
        token_type="Bearer",
        expires_in=3600,
        obtained_at=datetime.now(timezone.utc),
    )


def test_pagination_collects_all(monkeypatch):
    payloads = [
        {
            "value": [
                {"Date": "202001", "SignedData": 1, "Version": "public.Actual"},
                {"Date": "202002", "SignedData": 2, "Version": "public.Actual"},
            ],
            "nextLink": "http://next",
        },
        {
            "value": [
                {"Date": "202002", "SignedData": 2, "Version": "public.Actual"},
                {"Date": "202003", "SignedData": 3, "Version": "public.Actual"},
            ]
        },
    ]
    calls = {"count": 0}

    def fake_request_json(url, headers, timeout):
        value = payloads[calls["count"]]
        calls["count"] += 1
        return value

    monkeypatch.setattr(export_module, "_request_json", fake_request_json)
    monkeypatch.setattr(
        "sac_connector.timeseries.request_token", lambda _cfg: _mock_token()
    )
    monkeypatch.setattr(export_module.time, "sleep", lambda *_: None)

    config = SimpleNamespace(tenant_url="https://example.sap")
    df = fetch_timeseries("provider", config=config)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 4


def test_retry_on_429(monkeypatch):
    calls = {"count": 0}

    def fake_request_json(url, headers, timeout):
        calls["count"] += 1
        if calls["count"] == 1:
            raise export_module.ExportHttpError(429, "rate limited")
        return {"value": [{"Date": "202001", "SignedData": 1, "Version": "public.Actual"}]}

    monkeypatch.setattr(export_module, "_request_json", fake_request_json)
    monkeypatch.setattr(
        "sac_connector.timeseries.request_token", lambda _cfg: _mock_token()
    )
    monkeypatch.setattr(export_module.time, "sleep", lambda *_: None)

    config = SimpleNamespace(tenant_url="https://example.sap")
    df = fetch_timeseries("provider", config=config, page_size=1, max_rows=1)
    assert len(df) == 1


def test_timeseries_ignores_page_size_param(monkeypatch):
    captured = []

    def fake_request_json(url, headers, timeout):
        captured.append((url, headers))
        return {"value": []}

    monkeypatch.setattr(export_module, "_request_json", fake_request_json)
    monkeypatch.setattr(
        "sac_connector.timeseries.request_token", lambda _cfg: _mock_token()
    )

    config = SimpleNamespace(tenant_url="https://example.sap")
    fetch_timeseries("provider", config=config, page_size=50, max_rows=1)

    url, headers = captured[0]
    query = dict(parse.parse_qsl(parse.urlparse(url).query))
    assert "$top" not in query
    assert "$skip" not in query
    assert "Prefer" not in headers
