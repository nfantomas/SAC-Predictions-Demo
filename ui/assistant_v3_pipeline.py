from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import pandas as pd

from config import Assumptions, DEFAULT_ASSUMPTIONS
from llm.validate_suggestion import SuggestionValidationError
from llm.validate_v3 import ValidateContext, validate_and_sanitize
from model.driver_model import compute_alpha_beta, cost_from_fte, fte_from_cost, resolve_t0_cost
from scenarios.apply_scenario_v3 import apply_scenario_v3
from scenarios.schema import ScenarioParamsV3


@dataclass(frozen=True)
class DriverContext:
    alpha: float
    beta: float
    t0_cost_used: float
    warning: Optional[str]


def strip_json_fences(text: str) -> str:
    if not isinstance(text, str):
        return ""
    cleaned = text.strip()
    if cleaned.startswith("```") or cleaned.endswith("```") or cleaned.lower().startswith("json"):
        raise SuggestionValidationError("LLM response contained markdown/code fences.")
    return cleaned


def parse_suggestion(raw: str) -> Dict[str, object]:
    cleaned = strip_json_fences(raw)
    return json.loads(cleaned)


def build_driver_context(
    observed_t0_cost: float,
    assumptions: Assumptions = DEFAULT_ASSUMPTIONS,
) -> DriverContext:
    t0_cost_used, warning = resolve_t0_cost(
        observed_t0_cost=observed_t0_cost,
        configured_t0_cost=assumptions.t0_cost,
        mismatch_threshold=assumptions.mismatch_threshold,
    )
    alpha, beta = compute_alpha_beta(t0_cost_used, assumptions.fixed_cost_share, assumptions.t0_fte)
    return DriverContext(alpha=alpha, beta=beta, t0_cost_used=t0_cost_used, warning=warning)


def _cost_series_from_fte(fte_series: pd.Series, ctx: DriverContext) -> pd.Series:
    return fte_series.apply(lambda f: cost_from_fte(f, ctx.alpha, ctx.beta))


def _implied_fte_series(cost_series: pd.Series, ctx: DriverContext) -> pd.Series:
    return cost_series.apply(lambda c: fte_from_cost(c, ctx.alpha, ctx.beta))


def apply_driver_scenario(
    forecast_cost_df: pd.DataFrame,
    params: ScenarioParamsV3,
    driver: str,
    ctx: DriverContext,
    scenario_name: str = "assistant_v3",
) -> pd.DataFrame:
    if driver not in ("cost", "fte", "cost_target"):
        driver = "cost"

    baseline_cost = forecast_cost_df.copy()
    baseline_cost = baseline_cost[["date", "yhat"]].copy()
    baseline_cost["date"] = pd.to_datetime(baseline_cost["date"])

    if driver == "cost":
        return apply_scenario_v3(baseline_cost, params, scenario_name)

    if driver == "fte":
        implied_fte = _implied_fte_series(baseline_cost["yhat"], ctx)
        fte_baseline = pd.DataFrame({"date": baseline_cost["date"], "yhat": implied_fte})
        fte_scenario = apply_scenario_v3(fte_baseline, params, scenario_name)
        fte_scenario["yhat"] = _cost_series_from_fte(pd.to_numeric(fte_scenario["yhat"]), ctx)
        return fte_scenario

    # driver == "cost_target": treat as cost overlay but also provide implied FTE (optional)
    scenario = apply_scenario_v3(baseline_cost, params, scenario_name)
    return scenario


def validate_and_prepare_params(params: Dict[str, object]) -> Tuple[ScenarioParamsV3, list[str]]:
    try:
        return validate_and_sanitize(params, ctx=ValidateContext())
    except SuggestionValidationError:
        raise


def resolve_driver_and_params(
    suggestion: Dict[str, object],
    ctx: DriverContext,
    override_driver: str | None = None,
    horizon_months: int = 120,
) -> Tuple[str, ScenarioParamsV3, list[str], Dict[str, float]]:
    """
    Decide driver, validate params, and compute derived metrics.
    """
    override = (override_driver or "").strip().lower()
    driver_inferred = (suggestion.get("driver") or suggestion.get("suggested_driver") or "").lower()
    if driver_inferred not in ("cost", "fte", "cost_target"):
        raise SuggestionValidationError("LLM response missing a valid driver (cost|fte|cost_target).")
    driver_used = driver_inferred if override in ("", "auto") else override
    if driver_used not in ("cost", "fte", "cost_target"):
        raise SuggestionValidationError("Driver override must be one of cost|fte|cost_target.")

    raw_params = suggestion.get("params", {})
    params_v3, warnings = validate_and_sanitize(raw_params, ctx=ValidateContext(horizon_months=horizon_months))

    # If driver is FTE but only a level impact is provided (no explicit FTE deltas), convert impact to an FTE delta
    if driver_used == "fte" and params_v3.impact_mode == "level" and params_v3.impact_magnitude and not params_v3.fte_delta_pct and not params_v3.fte_delta_abs:
        params_v3 = params_v3.__class__(**{**params_v3.__dict__, "fte_delta_pct": params_v3.impact_magnitude, "impact_magnitude": 0.0})
        warnings.append("Interpreted level impact as FTE delta for fte driver to avoid double-counting alpha.")
    # If driver is cost_target and params missing cost_target_pct, pull from suggestion.cost_target.target_pct if present
    if driver_used == "cost_target" and (params_v3.cost_target_pct is None or params_v3.cost_target_pct == 0):
        target_block = suggestion.get("cost_target") or {}
        if target_block.get("target_pct") is not None:
            params_v3 = params_v3.__class__(**{**params_v3.__dict__, "cost_target_pct": target_block["target_pct"]})
            warnings.append("Filled cost_target_pct from cost_target block.")

    baseline_fte = fte_from_cost(ctx.t0_cost_used, ctx.alpha, ctx.beta)
    derived: Dict[str, float] = {"baseline_fte": baseline_fte, "alpha": ctx.alpha, "beta": ctx.beta}
    if driver_used == "cost_target" and params_v3.cost_target_pct is not None:
        target_cost = ctx.t0_cost_used * (1 + params_v3.cost_target_pct)
        implied_fte = fte_from_cost(target_cost, ctx.alpha, ctx.beta)
        derived["target_cost"] = target_cost
        derived["implied_fte_delta"] = implied_fte - baseline_fte
    if driver_used == "fte":
        if params_v3.fte_delta_pct is not None:
            derived["implied_fte_delta"] = baseline_fte * params_v3.fte_delta_pct
        if params_v3.fte_delta_abs is not None:
            derived["implied_fte_delta"] = params_v3.fte_delta_abs
    return driver_used, params_v3, warnings, derived
