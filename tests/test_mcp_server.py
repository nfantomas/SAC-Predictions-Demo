import pytest

from mcp_server import _filter_rows, _parse_iso_date


def test_parse_iso_date():
    assert _parse_iso_date("2020-01-01").isoformat() == "2020-01-01"
    with pytest.raises(ValueError):
        _parse_iso_date("202001")


def test_filter_rows_by_date():
    rows = [
        {"date": "2020-01-01", "value": "1"},
        {"date": "2020-02-01", "value": "2"},
        {"date": "2020-03-01", "value": "3"},
    ]
    filtered = _filter_rows(rows, start="2020-02-01", end="2020-03-01")
    assert [row["date"] for row in filtered] == ["2020-02-01", "2020-03-01"]

    with pytest.raises(ValueError):
        _filter_rows(rows, start="2020-04-01", end="2020-03-01")
