from __future__ import annotations

from typing import Optional, Tuple


def resolve_t0_cost(
    observed_t0_cost: Optional[float],
    configured_t0_cost: float,
    mismatch_threshold: float = 0.20,
) -> Tuple[float, Optional[str]]:
    """
    Choose t0 cost using observed value when it differs from configured by more than the threshold.
    Returns chosen cost and an optional warning string.
    """
    if observed_t0_cost is None:
        return configured_t0_cost, None
    if configured_t0_cost <= 0:
        return observed_t0_cost, "Configured t0 cost invalid; using observed."
    diff_ratio = abs(observed_t0_cost - configured_t0_cost) / configured_t0_cost
    if diff_ratio > mismatch_threshold:
        return observed_t0_cost, f"Assumption mismatch: observed t0 cost is {observed_t0_cost:.0f}; using observed for alpha/beta."
    return configured_t0_cost, None


def compute_alpha_beta(t0_cost: float, fixed_share: float, t0_fte: float) -> Tuple[float, float]:
    if t0_fte <= 0:
        raise ValueError("t0_fte must be positive.")
    if t0_cost < 0:
        raise ValueError("t0_cost must be non-negative.")
    if not 0 <= fixed_share <= 1:
        raise ValueError("fixed_share must be within [0, 1].")
    alpha = fixed_share * t0_cost
    beta = (1 - fixed_share) * t0_cost / t0_fte
    return alpha, beta


def cost_from_fte(fte: float, alpha: float, beta: float) -> float:
    return max(0.0, alpha + max(0.0, fte) * beta)


def fte_from_cost(cost: float, alpha: float, beta: float) -> float:
    if beta <= 0:
        raise ValueError("beta must be positive.")
    variable_cost = max(0.0, cost - max(0.0, alpha))
    return max(0.0, variable_cost / beta)
