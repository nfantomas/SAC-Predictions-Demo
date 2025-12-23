import types
from datetime import datetime

from sac_connector import export as export_module


def test_pagination_combines_rows(monkeypatch):
    payloads = [
        {"data": [{"date": "2024-01-01", "value": 1}], "nextLink": "http://next"},
        {"data": [{"date": "2024-02-01", "value": 2}]},
    ]
    calls = {"count": 0}

    def fake_request_json(url, headers, timeout):
        value = payloads[calls["count"]]
        calls["count"] += 1
        return value

    monkeypatch.setattr(export_module, "_request_json", fake_request_json)
    monkeypatch.setattr(
        export_module,
        "request_token",
        lambda _config: export_module.TokenInfo(
            access_token="token",
            token_type="Bearer",
            expires_in=3600,
            obtained_at=datetime.utcnow(),
        ),
    )

    rows = export_module.export_all(
        config=types.SimpleNamespace(),  # request_token is mocked below
        export_url="http://first",
        params=None,
    )
    assert rows == [
        {"date": "2024-01-01", "value": 1},
        {"date": "2024-02-01", "value": 2},
    ]


def test_retry_on_429(monkeypatch):
    calls = {"count": 0}

    def fake_request_json(url, headers, timeout):
        calls["count"] += 1
        if calls["count"] == 1:
            raise export_module.ExportHttpError(429, "rate limited")
        return {"data": [{"date": "2024-01-01", "value": 1}]}

    monkeypatch.setattr(export_module, "_request_json", fake_request_json)
    monkeypatch.setattr(export_module.time, "sleep", lambda *_: None)

    payload = export_module.request_json_with_retry("http://x", {}, timeout=1, max_attempts=2)
    assert payload["data"][0]["value"] == 1


def test_normalization_schema():
    rows = [{"period": "2024-01", "metric": "2.5", "region": "NA"}]
    normalized = export_module.normalize_rows(
        rows, date_field="period", value_field="metric", dim_fields=["region"], grain="month"
    )
    assert normalized == [{"date": "2024-01-01", "value": 2.5, "dim_region": "NA"}]
