from __future__ import annotations

from typing import Iterable, List, Tuple

import numpy as np
import pandas as pd

from config import BASELINE_INFLATION_PPY


def calibrate_alpha_beta(cost_t0: float, fte_t0: float, fixed_share: float) -> Tuple[float, float]:
    if fte_t0 <= 0:
        raise ValueError("fte_t0 must be positive.")
    if cost_t0 < 0:
        raise ValueError("cost_t0 must be non-negative.")
    if not 0 <= fixed_share <= 1:
        raise ValueError("fixed_share must be within [0, 1].")
    alpha = fixed_share * cost_t0
    beta0 = (1 - fixed_share) * cost_t0 / fte_t0
    return alpha, beta0


def project_beta(beta0: float, inflation_ppy: float = BASELINE_INFLATION_PPY, months: int = 120, level_resets: Iterable[float] | None = None) -> pd.Series:
    monthly_rate = (1 + inflation_ppy) ** (1 / 12.0) - 1
    betas: List[float] = []
    current = beta0
    for idx in range(months):
        if level_resets:
            for reset in level_resets:
                if reset != 0 and idx == 0:
                    current = current * (1.0 + reset)
        betas.append(current)
        current = current * (1.0 + monthly_rate)
    return pd.Series(betas)


def cost_from_fte(alpha: float, beta_series: pd.Series, fte_series: pd.Series) -> pd.Series:
    if len(beta_series) != len(fte_series):
        raise ValueError("beta_series and fte_series must align.")
    variable_cost = beta_series * fte_series.clip(lower=0.0)
    total_cost = alpha + variable_cost
    return total_cost.clip(lower=alpha)
