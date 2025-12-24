from dataclasses import dataclass
from datetime import date
from typing import Iterable, Optional

import pandas as pd


class NormalizeError(Exception):
    pass


@dataclass(frozen=True)
class NormalizeSpec:
    date_field: str = "Date"
    value_field: str = "SignedData"
    grain: str = "month"
    aggregate: str = "sum"


def _parse_yyyymm(value: str) -> date:
    if len(value) != 6 or not value.isdigit():
        raise NormalizeError(f"Invalid Date format (expected YYYYMM): {value}")
    year = int(value[:4])
    month = int(value[4:])
    if month < 1 or month > 12:
        raise NormalizeError(f"Invalid Date month: {value}")
    return date(year, month, 1)


def normalize_timeseries(
    df: pd.DataFrame,
    spec: NormalizeSpec = NormalizeSpec(),
    group_dims: Optional[Iterable[str]] = None,
) -> pd.DataFrame:
    if df.empty:
        raise NormalizeError("Empty dataset; check filters in docs/dataset_binding.md.")

    if spec.date_field not in df.columns or spec.value_field not in df.columns:
        raise NormalizeError("Missing required fields for normalization.")

    working = df[[spec.date_field, spec.value_field]].copy()
    working[spec.date_field] = working[spec.date_field].astype(str).map(_parse_yyyymm)
    working[spec.value_field] = pd.to_numeric(working[spec.value_field], errors="coerce")

    if working[spec.value_field].isna().any():
        raise NormalizeError("Non-numeric values found in measure column.")

    working["date"] = working[spec.date_field].map(lambda d: d.isoformat())
    working["value"] = working[spec.value_field].astype(float)

    group_cols = ["date"]
    if group_dims:
        for dim in group_dims:
            if dim in df.columns:
                working[f"dim_{dim}"] = df[dim].astype(str)
                group_cols.append(f"dim_{dim}")

    if spec.aggregate != "sum":
        raise NormalizeError(f"Unsupported aggregation: {spec.aggregate}")

    aggregated = working.groupby(group_cols, as_index=False)["value"].sum()
    return aggregated.sort_values("date").reset_index(drop=True)
