from __future__ import annotations

from typing import Tuple


def compute_alpha_beta(total_cost_t0: float, fixed_share: float, fte_t0: float) -> Tuple[float, float]:
    if fte_t0 <= 0:
        raise ValueError("fte_t0 must be positive.")
    if total_cost_t0 < 0:
        raise ValueError("total_cost_t0 must be non-negative.")
    if not 0 <= fixed_share <= 1:
        raise ValueError("fixed_share must be within [0, 1].")
    alpha = fixed_share * total_cost_t0
    beta = (1 - fixed_share) * total_cost_t0 / fte_t0
    return alpha, beta


def cost_from_fte(fte: float, alpha: float, beta: float) -> float:
    return max(0.0, alpha + max(0.0, fte) * beta)


def fte_from_cost(cost_target: float, alpha: float, beta: float) -> float:
    if beta <= 0:
        raise ValueError("beta must be positive.")
    variable = max(0.0, cost_target - max(0.0, alpha))
    return max(0.0, variable / beta)
