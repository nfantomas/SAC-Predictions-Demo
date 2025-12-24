from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Literal

import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing


logger = logging.getLogger(__name__)


Method = Literal["auto", "ets", "cagr"]


@dataclass(frozen=True)
class BaselineConfig:
    min_points_for_ets: int = 24
    horizon_months: int = 120
    cagr_damping: float = 0.8
    clip_non_negative: bool = True


def _ensure_monthly(df: pd.DataFrame) -> pd.Series:
    if "date" not in df.columns or "value" not in df.columns:
        raise ValueError("Input series must have date and value columns.")
    working = df[["date", "value"]].copy()
    working["date"] = pd.to_datetime(working["date"], errors="raise")
    working = working.sort_values("date")
    working = working.dropna()
    series = working.set_index("date")["value"].astype(float)
    return series


def _forecast_index(last_date: pd.Timestamp, horizon_months: int) -> pd.DatetimeIndex:
    start = (last_date + pd.offsets.MonthBegin()).normalize()
    return pd.date_range(start=start, periods=horizon_months, freq="MS")


def _fit_ets(series: pd.Series, horizon_months: int) -> pd.Series:
    model = ExponentialSmoothing(
        series,
        trend="add",
        seasonal=None,
        initialization_method="estimated",
    )
    fit = model.fit(optimized=True)
    forecast = fit.forecast(horizon_months)
    return forecast


def _fit_cagr(series: pd.Series, horizon_months: int, damping: float) -> pd.Series:
    first = series.iloc[0]
    last = series.iloc[-1]
    if first <= 0 or last < 0:
        raise ValueError("CAGR requires positive start and non-negative end values.")
    years = max(1, len(series) / 12.0)
    cagr = (last / first) ** (1 / years) - 1
    monthly_rate = (1 + cagr) ** (1 / 12.0) - 1
    monthly_rate *= damping
    values = []
    current = last
    for _ in range(horizon_months):
        current = current * (1 + monthly_rate)
        values.append(current)
    return pd.Series(values)


def run_baseline(
    series_df: pd.DataFrame,
    horizon_months: int = 120,
    method: Method = "auto",
    config: BaselineConfig = BaselineConfig(),
) -> pd.DataFrame:
    series = _ensure_monthly(series_df)
    if series.empty:
        raise ValueError("Input series is empty.")

    horizon = horizon_months or config.horizon_months
    method_used = method

    if method == "auto":
        if len(series) >= config.min_points_for_ets:
            method_used = "ets"
        else:
            method_used = "cagr"

    forecast = None
    if method_used == "ets":
        try:
            forecast = _fit_ets(series, horizon)
        except Exception as exc:
            logger.warning("ETS failed, falling back to CAGR: %s", exc)
            method_used = "cagr"
    if method_used == "cagr":
        forecast = _fit_cagr(series, horizon, config.cagr_damping)

    if forecast is None:
        raise ValueError("Forecast failed to produce output.")

    forecast_index = _forecast_index(series.index[-1], horizon)
    forecast = pd.Series(forecast.values, index=forecast_index)
    if config.clip_non_negative:
        forecast = forecast.clip(lower=0.0)

    output = pd.DataFrame(
        {
            "date": forecast.index.date.astype(str),
            "yhat": forecast.values.astype(float),
            "method": method_used,
        }
    )
    return output
