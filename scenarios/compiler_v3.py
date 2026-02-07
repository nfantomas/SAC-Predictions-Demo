from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from config import BASELINE_FTE_GROWTH_YOY
from llm.intent_schema import ScenarioIntent
from scenarios.schema import ScenarioParamsV3
from scenarios.templates import (
    attrition as attrition_tmpl,
    constraint as constraint_tmpl,
    mix_shift as mix_shift_tmpl,
    policy as policy_tmpl,
    productivity as productivity_tmpl,
    relocation as relocation_tmpl,
    shock as shock_tmpl,
    target as target_tmpl,
)


@dataclass(frozen=True)
class CompileResult:
    params_v3: ScenarioParamsV3
    human_summary: str
    assumptions: List[str]
    needs_clarification: bool
    clarifying_question: Optional[str]


def _month_diff(t0_start: str, start: str) -> int:
    t0 = datetime.strptime(t0_start, "%Y-%m")
    target = datetime.strptime(start, "%Y-%m")
    return (target.year - t0.year) * 12 + (target.month - t0.month)


def _default_pct(severity: str, direction: str) -> float:
    magnitude = {"operational": 0.05, "stress": 0.1, "crisis": 0.2}.get(severity, 0.05)
    if direction == "increase":
        return magnitude
    if direction == "decrease":
        return -magnitude
    return 0.0


def _resolve_magnitude(intent: ScenarioIntent) -> float:
    if intent.magnitude.type == "pct" and intent.magnitude.value is not None:
        return float(intent.magnitude.value)
    return _default_pct(intent.severity, intent.direction)


def compile_intent(
    intent: ScenarioIntent,
    *,
    t0_start: str | None = None,
    horizon_months: int = 120,
) -> CompileResult:
    needs_clarification = intent.need_clarification
    question = intent.clarifying_question
    lag_months = 0
    if t0_start:
        lag_months = _month_diff(t0_start, intent.timing.start)
    if lag_months < 0:
        # Fail-open: clamp start to t0 and continue with deterministic compile.
        lag_months = 0
        needs_clarification = True
        if not question:
            question = "Your requested start is before the forecast window. Should I start at t0 instead?"
    if lag_months >= horizon_months:
        return CompileResult(
            params_v3=ScenarioParamsV3(),
            human_summary="Timing falls outside the forecast horizon.",
            assumptions=[
                "Scenario timing is beyond the current horizon.",
                "Provide a start date within the forecast window.",
            ],
            needs_clarification=True,
            clarifying_question="Can you provide a start month within the forecast horizon?",
        )

    ramp_months = intent.timing.ramp_months
    duration_months = intent.timing.duration_months
    magnitude_pct = _resolve_magnitude(intent)

    constraints = set(intent.constraints)
    if "keep_cost_flat" in constraints:
        params = constraint_tmpl.build_cost_flat(lag_months, ramp_months)
    elif "keep_fte_flat" in constraints:
        params = constraint_tmpl.build_fte_flat(lag_months, ramp_months)
    elif intent.intent_type == "constraint":
        if intent.magnitude.type in ("pct", "abs", "yoy_cap") and (intent.magnitude.value not in (None, 0)):
            target_ramp = max(6, ramp_months)
            if "no_layoffs" in constraints and intent.direction == "decrease":
                # No-layoff plans should phase-in through attrition/redeployment.
                target_ramp = max(12, target_ramp)
            params = target_tmpl.build_params(lag_months, target_ramp, magnitude_pct)
        else:
            params = constraint_tmpl.build_cost_flat(lag_months, ramp_months)
    elif intent.intent_type == "policy":
        params = policy_tmpl.build_params(lag_months, ramp_months, duration_months, magnitude_pct)
    elif intent.intent_type == "shock":
        shock_duration = duration_months if duration_months is not None else 12
        params = shock_tmpl.build_params(lag_months, max(1, ramp_months), shock_duration, magnitude_pct)
    elif intent.intent_type == "target":
        target_ramp = max(6, ramp_months)
        if "no_layoffs" in constraints and intent.direction == "decrease":
            target_ramp = max(12, target_ramp)
        params = target_tmpl.build_params(lag_months, target_ramp, magnitude_pct)
    elif intent.intent_type == "mix_shift":
        params = mix_shift_tmpl.build_params(lag_months, ramp_months, magnitude_pct)
    elif intent.intent_type == "productivity":
        params = productivity_tmpl.build_params(lag_months, ramp_months, magnitude_pct)
    elif intent.intent_type == "attrition":
        params = attrition_tmpl.build_params(lag_months, ramp_months, magnitude_pct)
    elif intent.intent_type == "relocation":
        params = relocation_tmpl.build_params(lag_months, ramp_months, magnitude_pct)
    else:
        params = ScenarioParamsV3()

    if intent.intent_type == "other" and not needs_clarification:
        needs_clarification = True
        question = "Should this be modeled as a temporary shock or a permanent change?"

    summary = "Compiled scenario based on stated intent with a conservative default ramp."
    assumptions = [
        "Fixed share assumed ~20% at t0 with beta inflating ~3% per year.",
        "Baseline FTE growth ~3% per year; templates adjust around this.",
    ]
    if params.driver == "cost_target" and params.cost_target_pct == 0:
        summary = "Hold total HR costs flat and allow implied FTE to adjust over time."
    elif params.driver == "fte" and params.growth_delta_pp_per_year == -BASELINE_FTE_GROWTH_YOY:
        summary = "Freeze net hiring by offsetting baseline FTE growth."
    elif "no_layoffs" in constraints and params.driver == "cost_target" and (params.cost_target_pct or 0) < 0:
        summary = "Achieve cost reduction via gradual attrition, redeployment, and hiring slowdown with no layoffs."

    return CompileResult(
        params_v3=params,
        human_summary=summary,
        assumptions=assumptions,
        needs_clarification=needs_clarification,
        clarifying_question=question,
    )
