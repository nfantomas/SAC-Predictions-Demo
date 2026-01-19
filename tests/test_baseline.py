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
    # With baseline growth floor, forecast should continue upward from last observed.
    last_obs = 103.0
    min_monthly_rate = (1 + BaselineConfig().baseline_growth_ppy) ** (1 / 12.0) - 1
    expected_min = last_obs * (1 + min_monthly_rate)
    assert result["yhat"].iloc[0] >= expected_min * 0.99
    assert list(result["yhat"]) == sorted(result["yhat"])
