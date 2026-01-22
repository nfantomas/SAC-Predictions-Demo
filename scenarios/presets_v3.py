from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from config import DEFAULT_ASSUMPTIONS
from model.cost_driver import calibrate_alpha_beta
from scenarios.fte_planner import plan_fte_cuts
from scenarios.schema import ScenarioParamsV3


@dataclass(frozen=True)
class PresetV3:
    key: str
    description: str
    params: ScenarioParamsV3
    story: str
    expected_year1_delta_range: tuple[float, float]
    steady_state_note: Optional[str] = None
    implied_fte_cut: Optional[float] = None


def build_presets_v3() -> Dict[str, PresetV3]:
    assumptions = DEFAULT_ASSUMPTIONS
    alpha, beta = calibrate_alpha_beta(assumptions.t0_cost, assumptions.t0_fte, assumptions.fixed_cost_share)

    plan = plan_fte_cuts(
        cost_target_pct=-0.10,
        alpha=alpha,
        beta=beta,
        baseline_fte=assumptions.t0_fte,
        baseline_cost=assumptions.t0_cost,
    )
    implied_cut = -plan.total_fte_delta

    return {
        "freeze_hiring": PresetV3(
            key="freeze_hiring",
            description="Stop net hiring; growth slows to inflation-only (~3%/yr).",
            params=ScenarioParamsV3(
                driver="cost",
                lag_months=0,
                onset_duration_months=6,
                fte_delta_pct=0.0,
                growth_delta_pp_per_year=-0.03,  # from ~6% to ~3%
            ),
            story="Freeze headcount growth; cost drifts at inflation-only instead of 6% baseline.",
            expected_year1_delta_range=(-0.03, -0.01),
            steady_state_note="Parallel slope at ~3%/yr vs ~6% baseline.",
        ),
        "convert_it_contractors": PresetV3(
            key="convert_it_contractors",
            description="Convert contractors to employees; visible savings and parallel slope.",
            params=ScenarioParamsV3(
                driver="cost",
                lag_months=2,  # start a couple of months after t0 to align with baseline start
                onset_duration_months=10,  # gradual conversion over ~1 year
                beta_multiplier=0.90,
                impact_magnitude=0.0,  # start at baseline, savings come from beta ramp
                impact_mode="level",
            ),
            story="Reduce variable cost ~10% via gradual conversion over ~1 year starting at t0+2; line starts at baseline then drifts below with a parallel slope.",
            expected_year1_delta_range=(-0.09, -0.05),
            steady_state_note="Parallel slope below baseline.",
        ),
        "inflation_shock": PresetV3(
            key="inflation_shock",
            description="Permanent inflation shock to variable cost (+5%) starting mid next year (T+6).",
            params=ScenarioParamsV3(
                driver="cost",
                lag_months=6,
                onset_duration_months=3,
                beta_multiplier=1.05,
                impact_magnitude=0.0,
                impact_mode="level",
            ),
            story="Variable component up 5%; total rises ~4–6% then resumes 3% baseline slope.",
            expected_year1_delta_range=(0.04, 0.06),
            steady_state_note="Higher level, same growth slope.",
        ),
        "outsource_120_uk_cz": PresetV3(
            key="outsource_120_uk_cz",
            description="Outsource 120 FTE to CZ; moderate savings with ramp.",
            params=ScenarioParamsV3(
                driver="cost",
                lag_months=1,
                onset_duration_months=6,
                beta_multiplier=0.94,
                impact_magnitude=-0.02,
                impact_mode="level",
            ),
            story="~4–6% total savings after 6–12 months; keeps slope parallel.",
            expected_year1_delta_range=(-0.06, -0.04),
            steady_state_note="Lower level, same 3% slope.",
        ),
        "reduce_cost_10pct": PresetV3(
            key="reduce_cost_10pct",
            description="Hit a 10% cost target; compute implied FTE cut.",
            params=ScenarioParamsV3(
                driver="cost_target",
                lag_months=0,
                onset_duration_months=3,
                cost_target_pct=-0.10,
                fte_cut_plan=plan.cuts_by_seniority,
            ),
            story="Translate cost target into FTE cuts using alpha/beta; apply over 3 months.",
            expected_year1_delta_range=(-0.12, -0.08),
            steady_state_note="Cost reduced to target then grows at baseline 3%.",
            implied_fte_cut=implied_cut,
        ),
    }


PRESETS_V3 = build_presets_v3()
