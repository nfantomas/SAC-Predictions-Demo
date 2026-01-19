from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple


DEFAULT_SENIORITY_SHARES = {
    "Junior": 0.5,
    "Mid": 0.35,
    "Senior": 0.15,
}

DEFAULT_COST_MULTIPLIERS = {
    "Junior": 0.7,
    "Mid": 1.0,
    "Senior": 1.6,
}


@dataclass(frozen=True)
class FteCutPlan:
    total_fte_delta: float
    cuts_by_seniority: Dict[str, float]
    cost_multipliers: Dict[str, float]


def plan_fte_cuts(
    cost_target_pct: float,
    alpha: float,
    beta: float,
    baseline_fte: float,
    baseline_cost: float,
    seniority_shares: Dict[str, float] | None = None,
    cost_multipliers: Dict[str, float] | None = None,
) -> FteCutPlan:
    shares = seniority_shares or DEFAULT_SENIORITY_SHARES
    multipliers = cost_multipliers or DEFAULT_COST_MULTIPLIERS

    target_cost = baseline_cost * (1.0 + cost_target_pct)
    target_fte = max(0.0, (target_cost - max(0.0, alpha)) / beta) if beta > 0 else 0.0
    total_delta = target_fte - baseline_fte

    cuts: Dict[str, float] = {}
    for name, share in shares.items():
        baseline_cat = baseline_fte * share
        raw_cut = total_delta * share
        capped_cut = max(-baseline_cat, raw_cut)  # do not remove more than exists
        cuts[name] = capped_cut

    return FteCutPlan(total_fte_delta=total_delta, cuts_by_seniority=cuts, cost_multipliers=multipliers)
