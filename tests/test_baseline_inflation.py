import pandas as pd

from forecast.baseline import BaselineConfig, run_baseline


def test_baseline_inflation_trend_upward():
    dates = pd.date_range("2020-01-01", periods=24, freq="MS")
    series = pd.DataFrame({"date": dates.date.astype(str), "value": [10_000_000.0] * len(dates)})
    cfg = BaselineConfig(baseline_growth_ppy=0.06, baseline_inflation_ppy=0.03, min_points_for_ets=999)  # force CAGR path
    forecast = run_baseline(series, horizon_months=24, method="cagr", config=cfg)
    month0 = float(forecast["yhat"].iloc[0])
    month12 = float(forecast["yhat"].iloc[11])
    yoy_growth = (month12 / month0) - 1 if month0 else 0.0
    assert 0.054 <= yoy_growth <= 0.066  # around 6% per year by default


def test_baseline_growth_respects_config_override():
    dates = pd.date_range("2021-01-01", periods=24, freq="MS")
    series = pd.DataFrame({"date": dates.date.astype(str), "value": [8_000_000.0] * len(dates)})
    cfg = BaselineConfig(baseline_growth_ppy=0.08, min_points_for_ets=999)
    forecast = run_baseline(series, horizon_months=24, method="cagr", config=cfg)
    month0 = float(forecast["yhat"].iloc[0])
    month12 = float(forecast["yhat"].iloc[11])
    yoy_growth = (month12 / month0) - 1 if month0 else 0.0
    assert 0.072 <= yoy_growth <= 0.085
