from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Assumptions:
    t0_cost: float
    fixed_cost_share: float
    t0_fte: float
    mismatch_threshold: float

    @staticmethod
    def from_env(env: Optional[dict[str, str]] = None) -> "Assumptions":
        env = env or os.environ
        return Assumptions(
            t0_cost=float(env.get("T0_COST", 10_000_000)),
            fixed_cost_share=float(env.get("FIXED_COST_SHARE", 0.20)),
            t0_fte=float(env.get("T0_FTE", 800)),
            mismatch_threshold=float(env.get("T0_MISMATCH_THRESHOLD", 0.20)),
        )


DEFAULT_ASSUMPTIONS = Assumptions.from_env()
