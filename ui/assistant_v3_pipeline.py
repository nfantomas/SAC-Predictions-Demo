from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import pandas as pd

from config import Assumptions, DEFAULT_ASSUMPTIONS
from llm.validate_suggestion import SuggestionValidationError
from llm.validate_v3 import ValidateContext, validate_and_sanitize_result
from model.driver_model import compute_alpha_beta, cost_from_fte, fte_from_cost, resolve_t0_cost
from scenarios.apply_scenario_v3 import apply_scenario_v3
from scenarios.v3 import DriverContext as ScenarioDriverContext
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


def _infer_fte_direction(user_text: str | None) -> int:
    text = (user_text or "").lower()
    if not text:
        return 0
    positive_patterns = (
        r"\bbackfill\b",
        r"\breduced hours\b",
        r"\b4[- ]day workweek\b",
        r"\bfour[- ]day workweek\b",
        r"\badditional fte\b",
        r"\bincrease (?:fte|headcount|staff|workforce)\b",
        r"\badd (?:fte|headcount|staff)\b",
    )
    negative_patterns = (
        r"\breduce (?:fte|headcount|staff|workforce)\b",
        r"\bcut (?:fte|headcount|staff|workforce)\b",
        r"\blower (?:fte|headcount|staff|workforce)\b",
        r"\bdecrease (?:fte|headcount|staff|workforce)\b",
        r"\btrim (?:fte|headcount|staff|workforce)\b",
        r"\blayoff",
    )
    positive = any(re.search(p, text) for p in positive_patterns)
    negative = any(re.search(p, text) for p in negative_patterns)
    if positive and not negative:
        return 1
    if negative and not positive:
        return -1
    return 0


def _is_flat_cost_intent(user_text: str | None) -> bool:
    text = (user_text or "").lower()
    if not text:
        return False
    patterns = (
        r"\bkeep (total )?costs? (at current level|flat|constant|steady)\b",
        r"\bhold (total )?costs? (flat|constant|steady)\b",
        r"\bcosts? flat\b",
        r"\bkeep total labor cost flat\b",
    )
    return any(re.search(p, text) for p in patterns)


def _has_explicit_fte_change_request(user_text: str | None) -> bool:
    text = (user_text or "").lower()
    if not text:
        return False
    # Explicit action on workforce/FTE with a concrete magnitude ("reduce workforce by 10%").
    patterns = (
        r"\b(reduce|cut|lower|decrease|increase|raise|grow)\s+(our\s+)?(workforce|fte|headcount|staff)\b.*?\bby\s+\d+(\.\d+)?\s*%?",
        r"\b(reduce|cut|lower|decrease|increase|raise|grow)\s+(our\s+)?(workforce|fte|headcount|staff)\s+\d+(\.\d+)?\s*%?",
        r"\b(workforce|fte|headcount|staff)\s+(reduction|increase|cut)\s+of\s+\d+(\.\d+)?\s*%?",
    )
    return any(re.search(p, text) for p in patterns)


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
    ctx_adapter = ScenarioDriverContext(alpha=ctx.alpha, beta0=ctx.beta)

    scenario = apply_scenario_v3(baseline_cost, params, ctx_adapter, scenario_name)
    return scenario


def validate_and_prepare_params(params: Dict[str, object]) -> Tuple[ScenarioParamsV3, list[str], object]:
    params_v3, warnings, result = validate_and_sanitize_result(params, ctx=ValidateContext())
    return params_v3, warnings, result


def resolve_driver_and_params(
    suggestion: Dict[str, object],
    ctx: DriverContext,
    override_driver: str | None = None,
    horizon_months: int = 120,
    user_text: str | None = None,
) -> Tuple[str, ScenarioParamsV3, list[str], Dict[str, float], object]:
    """
    Decide driver, validate params, and compute derived metrics.
    """
    override = (override_driver or "").strip().lower()
    user_text_norm = (user_text or "").strip()
    flat_cost_intent = _is_flat_cost_intent(user_text_norm)
    explicit_fte_change = _has_explicit_fte_change_request(user_text_norm)
    scenario_driver = (suggestion.get("scenario_driver") or "auto").lower()
    driver_inferred = (suggestion.get("driver") or suggestion.get("suggested_driver") or "").lower()
    if scenario_driver == "auto":
        driver_used = driver_inferred
    else:
        driver_used = scenario_driver
    if driver_used not in ("cost", "fte", "cost_target"):
        raise SuggestionValidationError("LLM response missing a valid driver (cost|fte|cost_target).")
    driver_used = driver_used if override in ("", "auto") else override
    if driver_used not in ("cost", "fte", "cost_target"):
        raise SuggestionValidationError("Driver override must be one of cost|fte|cost_target.")

    # Keep-cost-flat questions should map to a cost_target constraint even when LLM returns cost.
    if flat_cost_intent and driver_used == "cost":
        driver_used = "cost_target"

    raw_params = suggestion.get("params", {})
    params_v3, warnings, val_result = validate_and_sanitize_result(raw_params, ctx=ValidateContext(horizon_months=horizon_months))

    # For FTE driver, avoid mixing explicit FTE deltas with level impact (double-count on cost path).
    if (
        driver_used == "fte"
        and params_v3.impact_mode == "level"
        and params_v3.impact_magnitude
        and (params_v3.fte_delta_pct is not None or params_v3.fte_delta_abs is not None)
    ):
        params_v3 = params_v3.__class__(**{**params_v3.__dict__, "impact_magnitude": 0.0})
        warnings.append("Ignored level impact for fte driver because explicit FTE delta was provided.")
    # If driver is FTE but only a level impact is provided (no explicit FTE deltas), convert impact to an FTE delta.
    if (
        driver_used == "fte"
        and params_v3.impact_mode == "level"
        and params_v3.impact_magnitude
        and params_v3.fte_delta_pct is None
        and params_v3.fte_delta_abs is None
    ):
        params_v3 = params_v3.__class__(
            **{**params_v3.__dict__, "fte_delta_pct": params_v3.impact_magnitude, "impact_magnitude": 0.0}
        )
        warnings.append("Interpreted level impact as FTE delta for fte driver to avoid double-counting alpha.")
    # If driver is cost_target and params missing cost_target_pct, pull from suggestion.cost_target.target_pct if present
    if driver_used == "cost_target" and (params_v3.cost_target_pct is None or params_v3.cost_target_pct == 0):
        target_block = suggestion.get("cost_target") or {}
        if target_block.get("target_pct") is not None:
            params_v3 = params_v3.__class__(**{**params_v3.__dict__, "cost_target_pct": target_block["target_pct"]})
            warnings.append("Filled cost_target_pct from cost_target block.")
    if driver_used == "cost_target" and params_v3.cost_target_pct is None and flat_cost_intent:
        params_v3 = params_v3.__class__(**{**params_v3.__dict__, "cost_target_pct": 0.0})
        warnings.append("Interpreted request as a flat cost target (0%).")
    if driver_used == "cost_target" and params_v3.cost_target_pct is None:
        raise SuggestionValidationError("Cost target driver requires cost_target_pct.")
    # Heuristic: only convert cost_target->fte when the user explicitly requests an FTE change action/value.
    if driver_used == "cost_target" and explicit_fte_change:
        fte_pct = params_v3.fte_delta_pct or params_v3.cost_target_pct
        params_v3 = params_v3.__class__(**{**params_v3.__dict__, "fte_delta_pct": fte_pct, "cost_target_pct": None})
        driver_used = "fte"
        warnings.append("Interpreted request as FTE reduction and applied fte_delta_pct instead of cost target.")

    # If user intent is a cost target but driver is FTE, translate cost target into the equivalent FTE delta using fixed/variable split.
    variable_share = 1.0
    if ctx.t0_cost_used:
        variable_share = max(1e-6, 1.0 - (ctx.alpha / ctx.t0_cost_used))
    if driver_used == "fte":
        target_cost_pct = params_v3.cost_target_pct
        target_block = suggestion.get("cost_target") or {}
        target_pct_fallback = target_block.get("target_pct")
        # Prefer explicit cost_target_pct; otherwise, if a cost_target block is present, translate it.
        if target_cost_pct is None and target_pct_fallback is not None:
            target_cost_pct = target_pct_fallback
        # If LLM inferred cost_target but stuffed it into fte_delta_pct, reinterpret it as a cost target value.
        if (
            target_cost_pct is None
            and driver_inferred == "cost_target"
            and params_v3.fte_delta_pct is not None
            and not explicit_fte_change
        ):
            target_cost_pct = params_v3.fte_delta_pct
        if target_cost_pct is not None:
            fte_pct_needed = target_cost_pct / variable_share
            params_v3 = params_v3.__class__(
                **{**params_v3.__dict__, "fte_delta_pct": fte_pct_needed, "cost_target_pct": None}
            )
            warnings.append(
                f"Translated cost target {target_cost_pct:+.1%} into FTE change {fte_pct_needed:+.1%} using variable share ≈ {variable_share:.2f}."
            )

    # Directional intent guardrail for FTE asks (e.g. backfill/reduced-hours should not come back as a cut).
    if driver_used == "fte":
        expected_dir = _infer_fte_direction(user_text)
        if expected_dir > 0:
            if params_v3.fte_delta_pct is not None and params_v3.fte_delta_pct < 0:
                params_v3 = params_v3.__class__(**{**params_v3.__dict__, "fte_delta_pct": abs(params_v3.fte_delta_pct)})
                warnings.append("Adjusted FTE delta sign to positive based on backfill/increase intent.")
            if params_v3.fte_delta_abs is not None and params_v3.fte_delta_abs < 0:
                params_v3 = params_v3.__class__(**{**params_v3.__dict__, "fte_delta_abs": abs(params_v3.fte_delta_abs)})
                warnings.append("Adjusted FTE absolute change sign to positive based on backfill/increase intent.")
        elif expected_dir < 0:
            if params_v3.fte_delta_pct is not None and params_v3.fte_delta_pct > 0:
                params_v3 = params_v3.__class__(**{**params_v3.__dict__, "fte_delta_pct": -abs(params_v3.fte_delta_pct)})
                warnings.append("Adjusted FTE delta sign to negative based on reduction intent.")
            if params_v3.fte_delta_abs is not None and params_v3.fte_delta_abs > 0:
                params_v3 = params_v3.__class__(**{**params_v3.__dict__, "fte_delta_abs": -abs(params_v3.fte_delta_abs)})
                warnings.append("Adjusted FTE absolute change sign to negative based on reduction intent.")

    baseline_fte = fte_from_cost(ctx.t0_cost_used, ctx.alpha, ctx.beta)
    derived: Dict[str, float] = {"baseline_fte": baseline_fte, "alpha": ctx.alpha, "beta": ctx.beta}
    driver_rationale = suggestion.get("driver_rationale")
    if driver_rationale:
        derived["driver_rationale"] = driver_rationale
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
    return driver_used, params_v3, warnings, derived, val_result
