from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict

import pandas as pd

from config import DEFAULT_ASSUMPTIONS
from llm.scenario_assistant_v3 import request_suggestion
from llm.validate_suggestion import SuggestionValidationError
from scenarios.schema import ScenarioParamsV3
from ui.assistant_v3_pipeline import (
    apply_driver_scenario,
    build_driver_context,
    parse_suggestion,
    resolve_driver_and_params,
)


FORECAST_PATH = Path("data/cache/forecast.csv")


def _fallback_forecast(months: int = 120) -> pd.DataFrame:
    dates = pd.date_range("2028-01-01", periods=months, freq="MS")
    values = [DEFAULT_ASSUMPTIONS.t0_cost]
    monthly_growth = (1.0 + 0.06) ** (1.0 / 12.0)
    for _ in range(1, months):
        values.append(values[-1] * monthly_growth)
    return pd.DataFrame({"date": dates, "yhat": values})


def _load_forecast() -> pd.DataFrame:
    if not FORECAST_PATH.exists():
        return _fallback_forecast()
    df = pd.read_csv(FORECAST_PATH)
    if df.empty or "date" not in df.columns or "yhat" not in df.columns:
        return _fallback_forecast()
    df = df[["date", "yhat"]].copy()
    df["date"] = pd.to_datetime(df["date"])
    return df


def _result_error(
    error_type: str,
    message: str,
    model_output_json: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    return {
        "error_type": error_type,
        "error_message": message,
        "model_output_json": model_output_json or {},
        "applied_params": {},
        "summary_text": "",
        "key_metrics": {
            "driver": "unknown",
            "warnings_count": 0,
            "deterministic_ten_year_multiplier": None,
            "clarification_required": False,
        },
    }


def _to_params_dict(params: ScenarioParamsV3) -> Dict[str, Any]:
    out = asdict(params)
    if isinstance(out.get("fte_cut_plan"), list):
        out["fte_cut_plan"] = [dict(x) for x in out["fte_cut_plan"]]
    return out


def generate_answer(question: str) -> Dict[str, Any]:
    forecast = _load_forecast()
    horizon_months = len(forecast)
    horizon_years = max(1, round(horizon_months / 12))
    observed_t0_cost = float(forecast["yhat"].iloc[0]) if not forecast.empty else DEFAULT_ASSUMPTIONS.t0_cost
    baseline_stats = {
        "last_value": observed_t0_cost,
        "trend_12m": observed_t0_cost * 0.06 / 12,
        "volatility": 0.01,
    }

    try:
        llm_out = request_suggestion(question, horizon_years=horizon_years, baseline_stats=baseline_stats)
    except Exception as exc:  # noqa: BLE001
        return _result_error("llm_error", str(exc))

    suggestion = llm_out.get("response")
    if isinstance(suggestion, str):
        try:
            suggestion = parse_suggestion(suggestion)
        except Exception as exc:  # noqa: BLE001
            return _result_error("parse_error", str(exc))
    if not isinstance(suggestion, dict):
        return _result_error("invalid_payload", "Model response is not an object.")

    if suggestion.get("need_clarification") is True:
        return {
            "error_type": "",
            "error_message": "",
            "model_output_json": suggestion,
            "applied_params": {},
            "summary_text": "",
            "key_metrics": {
                "driver": "unknown",
                "warnings_count": 0,
                "deterministic_ten_year_multiplier": None,
                "clarification_required": True,
                "clarifying_question": suggestion.get("clarifying_question", ""),
            },
        }

    try:
        ctx = build_driver_context(observed_t0_cost=observed_t0_cost, assumptions=DEFAULT_ASSUMPTIONS)
        driver_used, params_v3, warnings, _derived, val_result = resolve_driver_and_params(
            suggestion=suggestion,
            ctx=ctx,
            override_driver=None,
            horizon_months=horizon_months,
            user_text=question,
        )
    except SuggestionValidationError as exc:
        return _result_error("validation_error", str(exc), model_output_json=suggestion)
    except Exception as exc:  # noqa: BLE001
        return _result_error("pipeline_error", str(exc), model_output_json=suggestion)

    try:
        overlay = apply_driver_scenario(
            forecast_cost_df=forecast,
            params=params_v3,
            driver=driver_used,
            ctx=ctx,
            scenario_name="eval_generated",
        )
    except Exception as exc:  # noqa: BLE001
        return _result_error("apply_error", str(exc), model_output_json=suggestion)

    base_last = float(forecast["yhat"].iloc[-1]) if not forecast.empty else 0.0
    scen_last = float(overlay["yhat"].iloc[-1]) if not overlay.empty else 0.0
    det_multiplier = None
    if base_last > 0:
        det_multiplier = round(scen_last / base_last, 4)

    rationale = suggestion.get("rationale") or {}
    summary_text = rationale.get("summary", "") if isinstance(rationale, dict) else ""
    warning_count = len(warnings) + len(getattr(val_result, "warnings", [])) + len(getattr(val_result, "clamps", []))

    return {
        "error_type": "",
        "error_message": "",
        "model_output_json": suggestion,
        "applied_params": _to_params_dict(params_v3),
        "summary_text": summary_text,
        "key_metrics": {
            "driver": driver_used,
            "warnings_count": warning_count,
            "deterministic_ten_year_multiplier": det_multiplier,
            "clarification_required": False,
            "provider": llm_out.get("provider"),
            "model": llm_out.get("model"),
            "fallback_used": llm_out.get("fallback_used", False),
        },
    }
