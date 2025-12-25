from dataclasses import dataclass
from typing import Iterable, Optional


@dataclass(frozen=True)
class OverrideParams:
    growth_delta_pp: float
    shock_year: Optional[int]
    shock_pct: float
    drift_pp_per_year: float


def validate_overrides(
    forecast_years: Iterable[int],
    shock_year: Optional[int],
    shock_pct: float,
    growth_delta_pp: float,
) -> None:
    years = set(forecast_years)
    if shock_year is not None and shock_year not in years:
        raise ValueError("shock_year must be within forecast horizon years.")
    if shock_pct < -0.9 or shock_pct > 1.0:
        raise ValueError("shock_pct must be within [-0.9, 1.0].")
    if growth_delta_pp < -0.5 or growth_delta_pp > 0.5:
        raise ValueError("growth_delta_pp_per_year out of range.")
