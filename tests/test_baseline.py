import pandas as pd
import pytest

from forecast.baseline import BaselineConfig, run_baseline


def _make_series(months: int, start_value: float = 100.0) -> pd.DataFrame:
    dates = pd.date_range("2020-01-01", periods=months, freq="MS")
    values = [start_value + i for i in range(months)]
    return pd.DataFrame({"date": dates.date.astype(str), "value": values})


def test_auto_selects_cagr_for_short_series():
    df = _make_series(12)
    result = run_baseline(df, horizon_months=3, method="auto")
    assert len(result) == 3
    assert set(result["method"]) == {"cagr"}


def test_auto_selects_ets_for_long_series():
    df = _make_series(36)
    result = run_baseline(df, horizon_months=3, method="auto")
    assert len(result) == 3
    assert set(result["method"]) == {"ets"}


def test_output_dates_and_non_negative():
    df = _make_series(24, start_value=10.0)
    result = run_baseline(df, horizon_months=2, method="cagr")
    assert list(result["date"]) == ["2022-01-01", "2022-02-01"]
    assert (result["yhat"] >= 0).all()


def test_ets_failure_falls_back(monkeypatch):
    df = _make_series(36)

    def fail_fit(*_args, **_kwargs):
        raise RuntimeError("ETS broken")

    monkeypatch.setattr("forecast.baseline._fit_ets", fail_fit)
    result = run_baseline(df, horizon_months=2, method="auto")
    assert set(result["method"]) == {"cagr"}


def test_regression_fixture_tolerance():
    df = pd.DataFrame(
        {
            "date": ["2020-01-01", "2020-02-01", "2020-03-01", "2020-04-01"],
            "value": [100.0, 101.0, 102.0, 103.0],
        }
    )
    result = run_baseline(
        df,
        horizon_months=3,
        method="cagr",
        config=BaselineConfig(cagr_damping=0.0),
    )
    expected = [103.0, 103.0, 103.0]
    for idx, value in enumerate(expected):
        assert result["yhat"].iloc[idx] == pytest.approx(value, rel=0.01)
