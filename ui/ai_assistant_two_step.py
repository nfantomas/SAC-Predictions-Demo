from __future__ import annotations

import pandas as pd
import streamlit as st

from config import DEFAULT_ASSUMPTIONS
from llm.intent_interpreter import interpret_intent
from llm.intent_schema import ScenarioIntent
from llm.validate_v3 import ValidateContext, validate_and_sanitize_result
from narrative.generator import summarize_series
from scenarios.compiler_v3 import compile_intent
from types import SimpleNamespace
from ui.apply_suggestion import set_pending_v3
from ui.assistant_v3_pipeline import apply_driver_scenario, build_driver_context
from ui.warnings import summarize_warnings


def _parse_optional_int(val: str) -> int | None:
    v = val.strip()
    return int(v) if v else None


def _parse_optional_float(val: str) -> float | None:
    v = val.strip()
    return float(v) if v else None


def _build_rationale(intent_data: dict, summary: str, assumptions: list[str], params) -> dict:
    timing = f"starts at T+{params.lag_months}m; ramp {params.onset_duration_months}m"
    impact = "no explicit level impact"
    if params.impact_mode == "level" and params.impact_magnitude:
        impact = f"level impact {params.impact_magnitude:+.1%}"
    elif params.impact_mode == "growth" and params.growth_delta_pp_per_year:
        impact = f"growth delta {params.growth_delta_pp_per_year*100:+.1f}pp/yr"
    return {
        "title": "Two-step compiled scenario",
        "summary": summary,
        "why_these_numbers": [
            f"Intent interpreted as {intent_data.get('intent_type')} with driver {params.driver}.",
            f"Timing: {timing}; {impact}.",
        ],
        "assumptions": assumptions,
        "sanity_checks": {
            "ten_year_multiplier_estimate": "",
            "notes": f"Severity tier: {intent_data.get('severity', 'operational')}.",
        },
    }


def _seed_two_step_editor(params) -> None:
    st.session_state["two_step_lag_months"] = int(params.lag_months)
    st.session_state["two_step_onset_duration_months"] = int(params.onset_duration_months)
    st.session_state["two_step_event_duration_months"] = "" if params.event_duration_months is None else str(params.event_duration_months)
    st.session_state["two_step_recovery_duration_months"] = "" if params.recovery_duration_months is None else str(params.recovery_duration_months)
    st.session_state["two_step_shape"] = params.shape
    st.session_state["two_step_impact_mode"] = params.impact_mode
    st.session_state["two_step_impact_magnitude"] = str(params.impact_magnitude)
    st.session_state["two_step_growth_delta"] = str(params.growth_delta_pp_per_year)
    st.session_state["two_step_drift"] = str(params.drift_pp_per_year)
    st.session_state["two_step_beta_multiplier"] = "" if params.beta_multiplier is None else str(params.beta_multiplier)
    st.session_state["two_step_fte_delta_abs"] = "" if params.fte_delta_abs is None else str(params.fte_delta_abs)
    st.session_state["two_step_fte_delta_pct"] = "" if params.fte_delta_pct is None else str(params.fte_delta_pct)
    st.session_state["two_step_cost_target_pct"] = "" if params.cost_target_pct is None else str(params.cost_target_pct)


def _params_from_editor(base_params):
    return base_params.__class__(
        driver=base_params.driver,
        lag_months=int(st.session_state.get("two_step_lag_months", 0)),
        onset_duration_months=int(st.session_state.get("two_step_onset_duration_months", 0)),
        event_duration_months=_parse_optional_int(str(st.session_state.get("two_step_event_duration_months", ""))),
        recovery_duration_months=_parse_optional_int(str(st.session_state.get("two_step_recovery_duration_months", ""))),
        shape=st.session_state.get("two_step_shape", base_params.shape),
        impact_mode=st.session_state.get("two_step_impact_mode", base_params.impact_mode),
        impact_magnitude=float(str(st.session_state.get("two_step_impact_magnitude", "0")).strip() or 0.0),
        growth_delta_pp_per_year=float(str(st.session_state.get("two_step_growth_delta", "0")).strip() or 0.0),
        drift_pp_per_year=float(str(st.session_state.get("two_step_drift", "0")).strip() or 0.0),
        beta_multiplier=_parse_optional_float(str(st.session_state.get("two_step_beta_multiplier", ""))),
        fte_delta_abs=_parse_optional_float(str(st.session_state.get("two_step_fte_delta_abs", ""))),
        fte_delta_pct=_parse_optional_float(str(st.session_state.get("two_step_fte_delta_pct", ""))),
        cost_target_pct=_parse_optional_float(str(st.session_state.get("two_step_cost_target_pct", ""))),
    )


def render_two_step_assistant(series_df: pd.DataFrame, forecast: pd.DataFrame, last_actual_value: float) -> None:
    st.subheader("AI scenario assistant (two-step)")
    st.caption("Interpreter → Compiler flow; always returns a safe default or a single clarification.")
    assistant_two_step_text = st.text_area(
        "Describe a scenario (two-step)",
        key="assistant_two_step_text",
        placeholder="e.g., keep costs flat and avoid layoffs",
    )
    if st.button("Interpret & compile", key="assistant_two_step_interpret"):
        stats = summarize_series(series_df)
        intent_result = interpret_intent(assistant_two_step_text, stats)
        try:
            intent = ScenarioIntent.model_validate(intent_result["intent"])
        except Exception as exc:
            st.error(f"Intent parse failed: {exc}")
            intent = None
        if intent:
            t0_start = pd.to_datetime(forecast["date"].iloc[0]).strftime("%Y-%m")
            compiled = compile_intent(intent, t0_start=t0_start, horizon_months=len(forecast))
            st.session_state["assistant_two_step_payload"] = {
                "intent": intent.model_dump(),
                "compiled": compiled,
            }
            st.session_state["assistant_two_step_params"] = compiled.params_v3
            _seed_two_step_editor(compiled.params_v3)
            st.session_state["assistant_two_step_override"] = False

    payload = st.session_state.get("assistant_two_step_payload")
    if not payload:
        return

    intent_data = payload["intent"]
    compiled = payload["compiled"]
    st.markdown(
        f"**Understood intent**: {intent_data.get('intent_type')} "
        f"({intent_data.get('direction')}) starting {intent_data.get('timing', {}).get('start', 'n/a')}. "
        f"Severity: {intent_data.get('severity')}."
    )
    st.write(compiled.human_summary)
    if compiled.assumptions:
        st.markdown("Assumptions")
        for item in compiled.assumptions:
            st.markdown(f"- {item}")
    if compiled.needs_clarification:
        st.warning(compiled.clarifying_question or "Clarification needed.")
        if st.button("Apply safe default anyway", key="assistant_two_step_apply_default"):
            st.session_state["assistant_two_step_override"] = True

    params_v3 = st.session_state.get("assistant_two_step_params", compiled.params_v3)
    ctx = build_driver_context(observed_t0_cost=last_actual_value, assumptions=DEFAULT_ASSUMPTIONS)
    c1, c2, c3 = st.columns(3)
    c1.metric("t0 cost used", f"{ctx.t0_cost_used:,.0f} EUR")
    c2.metric("Beta (per FTE)", f"{ctx.beta:,.0f}")
    c3.metric("Alpha (fixed)", f"{ctx.alpha:,.0f}")

    with st.expander("Proposed parameters", expanded=False):
        c1, c2 = st.columns(2)
        c1.number_input("Lag (months)", min_value=0, step=1, key="two_step_lag_months")
        c1.number_input("Ramp duration (months)", min_value=0, step=1, key="two_step_onset_duration_months")
        c1.text_input("Event duration (months, optional)", key="two_step_event_duration_months")
        c1.text_input("Recovery duration (months, optional)", key="two_step_recovery_duration_months")
        c1.selectbox("Profile shape", options=["step", "linear", "exp"], key="two_step_shape")
        c1.selectbox("Impact mode", options=["level", "growth"], key="two_step_impact_mode")
        c1.text_input("Impact magnitude (%)", key="two_step_impact_magnitude")
        c1.text_input("Growth delta (pp/year)", key="two_step_growth_delta")
        c1.text_input("Drift (pp/year)", key="two_step_drift")
        c2.text_input("Beta multiplier", key="two_step_beta_multiplier")
        c2.text_input("FTE delta (abs)", key="two_step_fte_delta_abs")
        c2.text_input("FTE delta (%)", key="two_step_fte_delta_pct")
        c2.text_input("Cost target (%)", key="two_step_cost_target_pct")

    try:
        params_v3 = _params_from_editor(params_v3)
    except ValueError as exc:
        st.error(f"Invalid parameter value: {exc}")
        return
    st.session_state["assistant_two_step_params"] = params_v3

    validated_params, validation_warnings, val_result = validate_and_sanitize_result(
        params_v3.__dict__,
        ctx=ValidateContext(horizon_months=len(forecast), severity=intent_data.get("severity", "operational")),
    )
    warning_msgs = validation_warnings + [w.message for w in getattr(val_result, "warnings", [])]
    clamp_msgs = [c.message for c in getattr(val_result, "clamps", [])]
    normalization_msgs = [m for m in warning_msgs if m.startswith("Normalized ")]
    warning_msgs = [m for m in warning_msgs if m not in normalization_msgs]
    summary_warnings, detail_warnings = summarize_warnings(warning_msgs, clamp_msgs, normalization_msgs)

    if val_result.errors:
        for issue in val_result.errors:
            st.error(issue.message)
        return
    if summary_warnings:
        st.markdown("**Warnings summary**")
        for item in summary_warnings:
            st.markdown(f"- {item}")
    with st.expander("Show details"):
        for item in detail_warnings:
            st.markdown(f"- {item}")

    if compiled.needs_clarification and not st.session_state.get("assistant_two_step_override"):
        st.info("Clarification needed before applying.")
        return

    # Publish into the same pending flow used by one-step assistant so UX/logic stay aligned.
    rationale = _build_rationale(intent_data, compiled.human_summary, compiled.assumptions, validated_params)
    derived = {
        "alpha": ctx.alpha,
        "beta": ctx.beta,
        "baseline_fte": max(0.0, (ctx.t0_cost_used - ctx.alpha) / ctx.beta) if ctx.beta else 0.0,
    }
    set_pending_v3(
        params=validated_params,
        driver_choice=validated_params.driver,
        ctx=SimpleNamespace(alpha=ctx.alpha, beta=ctx.beta, t0_cost_used=ctx.t0_cost_used, warning=ctx.warning),
        rationale=rationale,
        warnings=detail_warnings,
        safety={"warnings": [compiled.clarifying_question] if compiled.needs_clarification else []},
        raw_suggestion={"intent": intent_data},
        label=f"AI Assistant (Two-step) [{validated_params.driver}]",
        derived=derived,
    )

    if st.button("Apply parameters", key="assistant_two_step_apply"):
        scenario_df = apply_driver_scenario(
            forecast_cost_df=forecast[["date", "yhat"]],
            params=validated_params,
            driver=validated_params.driver,
            ctx=ctx,
            scenario_name="assistant_two_step",
        )
        st.session_state["assistant_v3_overlay"] = scenario_df
        st.session_state["assistant_v3_label"] = "AI Assistant (Two-step)"
        st.session_state["scenario_params_current"] = validated_params
        st.session_state["scenario_driver_current"] = validated_params.driver
        st.session_state["scenario_ctx_alpha"] = ctx.alpha
        st.session_state["scenario_ctx_beta"] = ctx.beta
        st.session_state["scenario_ctx_t0"] = ctx.t0_cost_used
        st.session_state["scenario_label_current"] = st.session_state["assistant_v3_label"]
        st.session_state["scenario_warnings_current"] = detail_warnings
        st.success("Compiled parameters applied. Overlay updated.")
        st.rerun()
