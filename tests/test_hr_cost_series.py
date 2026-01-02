import pandas as pd
import pytest

from pipeline.hr_cost_series import get_hr_cost_series


def test_hr_cost_series_fixture(tmp_path):
    cache_path = tmp_path / "series.csv"
    df, meta = get_hr_cost_series(source="fixture", cache_path=str(cache_path))
    assert not df.empty
    assert set(df.columns) >= {"date", "value"}
    assert meta["metric_name"] == "hr_cost"
    assert meta["currency"]
    assert meta["grain"]


def test_hr_cost_series_fixture_fte_mode(tmp_path, monkeypatch):
    monkeypatch.setenv("HR_SERIES_MODE", "fte")
    cache_path = tmp_path / "series.csv"
    df, meta = get_hr_cost_series(source="fixture", cache_path=str(cache_path))
    assert not df.empty
    assert meta["metric_name"] == "fte"
    assert meta["currency"] == ""
    assert df["value"].iloc[0] == pytest.approx(100.0)
