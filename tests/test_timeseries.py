from datetime import datetime
from types import SimpleNamespace

import pandas as pd

from sac_connector import export as export_module
from sac_connector.timeseries import fetch_timeseries


def _mock_token():
    return export_module.TokenInfo(
        access_token="token",
        token_type="Bearer",
        expires_in=3600,
        obtained_at=datetime.utcnow(),
    )


def test_pagination_dedup(monkeypatch):
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
    assert len(df) == 3


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
