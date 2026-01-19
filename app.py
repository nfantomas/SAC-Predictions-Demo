from __future__ import annotations

import json
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from config import BASELINE_GROWTH_YOY, BASELINE_INFLATION_PPY, DEFAULT_ASSUMPTIONS
from narrative.generator import summarize_series
from narrative.scenario_assistant import suggest_scenario
from llm.provider import LLMError
from llm.scenario_assistant_v3 import request_suggestion
from llm.validate_suggestion import SuggestionValidationError
from model.cost_driver import calibrate_alpha_beta
from pipeline.cache import CacheError, load_cache, load_cache_meta_raw
from pipeline.run_all import run_all
from scenarios.overlay_v2 import ScenarioParamsV2, apply_scenario_v2
from scenarios.presets_v2 import PRESETS_V2
from scenarios.presets_v3 import PRESETS_V3, PresetV3
from scenarios.schema import ScenarioParamsV3
from scenarios.validate import validate_params
from scenarios.validate_v3 import validate_projection
from scenarios.v3 import DriverContext, apply_scenario_v3_simple
from ui.apply_suggestion import clear_pending_v3, get_pending_v3, set_pending_v3
from ui.assistant_v3_pipeline import apply_driver_scenario, build_driver_context, parse_suggestion, validate_and_prepare_params
from ui.scenario_controls import validate_overrides


CACHE_SERIES_PRIMARY = Path("data/cache/sac_export_cost.csv")
CACHE_SERIES_FALLBACK = Path("data/cache/sac_export.csv")
CACHE_FORECAST = Path("data/cache/forecast.csv")
CACHE_SCENARIOS = Path("data/cache/scenarios.csv")


def _safe_error_text(value: object) -> str:
    try:
        text = str(value)
    except Exception:
        return "unknown error"
    try:
        text.encode("utf-8")
        return text
    except UnicodeEncodeError:
        return text.encode("ascii", "replace").decode("ascii")


def _load_series():
    series_path = CACHE_SERIES_PRIMARY if CACHE_SERIES_PRIMARY.exists() else CACHE_SERIES_FALLBACK
    rows, meta = load_cache(data_path=str(series_path))
    return rows, meta, series_path


def _display_metric_name(metric_name: str) -> str:
    name = metric_name.strip().lower()
    if name == "hr_cost":
        return "HR Cost"
    if name == "fte":
        return "FTE"
    return metric_name.replace("_", " ").title() if metric_name else "Series"


def _display_unit(unit: str) -> str:
    if not unit:
        return ""
    if unit.lower() == "fte":
        return "FTE"
    return unit.replace("_", " ")


def _implied_fte(cost: float, alpha: float, beta: float) -> float:
    return max(0.0, (cost - alpha) / beta)


def _is_headcount(metric_name: str, unit: str) -> bool:
    combined = f"{metric_name} {unit}".lower()
    return "fte" in combined or "headcount" in combined


def _load_forecast() -> pd.DataFrame:
    if not CACHE_FORECAST.exists():
        raise FileNotFoundError("forecast")
    df = pd.read_csv(CACHE_FORECAST)
    if df.empty:
        raise ValueError("forecast empty")
    df["date"] = pd.to_datetime(df["date"])
    return df


def _load_scenarios() -> pd.DataFrame:
    if not CACHE_SCENARIOS.exists():
        raise FileNotFoundError("scenarios")
    df = pd.read_csv(CACHE_SCENARIOS)
    if df.empty:
        raise ValueError("scenarios empty")
    df["date"] = pd.to_datetime(df["date"])
    return df


def _impact_preview(
    forecast_df: pd.DataFrame, params: ScenarioParamsV2, years: tuple[int, ...] = (1, 5, 10)
) -> list[tuple[int, float, float]]:
    scenario_df = apply_scenario_v2(forecast_df[["date", "yhat"]], params, "preview")
    scenario_df["date"] = pd.to_datetime(scenario_df["date"])
    base_year = int(forecast_df["date"].dt.year.min())
    rows = []
    for offset in years:
        target_year = base_year + (offset - 1)
        base_slice = forecast_df[forecast_df["date"].dt.year == target_year]
        scen_slice = scenario_df[scenario_df["date"].dt.year == target_year]
        if base_slice.empty or scen_slice.empty:
            continue
        base_val = float(base_slice.iloc[-1]["yhat"])
        scen_val = float(scen_slice.iloc[-1]["yhat"])
        delta = scen_val - base_val
        pct = delta / base_val if base_val else 0.0
        rows.append((offset, delta, pct))
    return rows


def _normalize_preset_name(name: str) -> str:
    if name == "baseline":
        return "base"
    return name


def _scenario_params_table(params: ScenarioParamsV3) -> pd.DataFrame:
    data = {
        "lag_months": params.lag_months,
        "onset_duration_months": params.onset_duration_months,
        "event_duration_months": params.event_duration_months,
        "recovery_duration_months": params.recovery_duration_months,
        "shape": params.shape,
        "impact_mode": params.impact_mode,
        "impact_magnitude": params.impact_magnitude,
        "growth_delta_pp_per_year": params.growth_delta_pp_per_year,
        "drift_pp_per_year": params.drift_pp_per_year,
        "event_growth_delta_pp_per_year": params.event_growth_delta_pp_per_year,
        "event_growth_exp_multiplier": params.event_growth_exp_multiplier,
        "post_event_growth_pp_per_year": params.post_event_growth_pp_per_year,
    }
    return pd.DataFrame([data]).T.reset_index().rename(columns={"index": "param", 0: "value"})


def _inject_styles() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;600&family=IBM+Plex+Serif:wght@500;700&display=swap');
        :root {
          --bg: #f4f1ea;
          --card: #fff7e8;
          --accent: #c14b2a;
          --ink: #2a2320;
        }
        .stApp {
          background: radial-gradient(1200px 600px at 10% -10%, #ffd7b5 0, transparent 60%),
                      radial-gradient(1000px 500px at 90% 0%, #e8d7ff 0, transparent 55%),
                      var(--bg);
          color: var(--ink);
          font-family: "IBM Plex Sans", sans-serif;
        }
        .app-title {
          font-family: "IBM Plex Serif", serif;
          font-size: 2rem;
          margin-bottom: 0.2rem;
        }
        .card {
          background: var(--card);
          border: 1px solid rgba(0,0,0,0.08);
          border-radius: 14px;
          padding: 1rem 1.2rem;
          box-shadow: 0 8px 24px rgba(0,0,0,0.08);
        }
        .meta-grid {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 0.5rem 1rem;
          font-size: 0.95rem;
        }
        .meta-key { color: #5a4d44; font-weight: 600; }
        .meta-val { color: #1f1a17; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(page_title="SAC Forecast Demo", layout="wide")
    _inject_styles()

    try:
        rows, meta, series_path = _load_series()
        meta_raw = load_cache_meta_raw()
    except CacheError:
        st.error("Series cache missing. Run `python -m demo.refresh --source sac` first.")
        return

    try:
        forecast = _load_forecast()
    except FileNotFoundError:
        st.error("Forecast cache missing. Run `python -m demo.forecast` first.")
        return
    except ValueError:
        st.error("Forecast cache empty. Run `python -m demo.forecast` first.")
        return

    try:
        scenarios = _load_scenarios()
    except FileNotFoundError:
        st.error("Scenario cache missing. Run `python -m demo.scenarios` first.")
        return
    except ValueError:
        st.error("Scenario cache empty. Run `python -m demo.scenarios` first.")
        return

    metric_name = str(meta_raw.get("metric_name", ""))
    unit = str(meta_raw.get("unit", ""))
    currency = str(meta_raw.get("currency", ""))
    grain = meta_raw.get("grain", "monthly")
    grain_label = "monthly" if grain in ("month", "monthly") else grain
    metric_label = _display_metric_name(metric_name)
    unit_label = currency or _display_unit(unit)
    title_unit = unit_label if unit_label.lower() != metric_label.lower() else ""
    title_suffix = f"{grain_label}" + (f", {title_unit}" if title_unit else "")

    st.markdown(
        f'<div class="app-title">{metric_label} ({title_suffix})</div>',
        unsafe_allow_html=True,
    )
    st.caption("Actuals from SAP Analytics Cloud • Forecast + scenarios • Adjustable assumptions")

    series_df = pd.DataFrame(rows)
    series_df["date"] = pd.to_datetime(series_df["date"])
    series_df["value"] = pd.to_numeric(series_df["value"], errors="coerce")
    series_df = series_df.sort_values("date")

    last_actual_value = float(series_df["value"].iloc[-1])
    last_actual_date = series_df["date"].iloc[-1]
    use_average = _is_headcount(metric_name, unit)
    if use_average:
        next_12_value = float(forecast["yhat"].iloc[:12].mean())
        year10_value = float(forecast["yhat"].iloc[-12:].mean())
    else:
        next_12_value = float(forecast["yhat"].iloc[:12].sum())
        year10_value = float(forecast["yhat"].iloc[-12:].sum())

    if "pending_preset" in st.session_state:
        st.session_state["selected_preset"] = _normalize_preset_name(
            st.session_state.pop("pending_preset")
        )
    if "selected_preset_v2" not in st.session_state:
        st.session_state["selected_preset_v2"] = "base"
    selected_preset = _normalize_preset_name(st.session_state["selected_preset_v2"])
    if selected_preset not in PRESETS_V2:
        selected_preset = "base"
        st.session_state["selected_preset_v2"] = "base"
    if use_average:
        base_year5 = float(forecast["yhat"].iloc[48:60].mean())
    else:
        base_year5 = float(forecast["yhat"].iloc[48:60].sum())
    selected_rows = scenarios[scenarios["scenario"] == selected_preset]
    if use_average:
        selected_year5 = (
            float(selected_rows["yhat"].iloc[48:60].mean()) if not selected_rows.empty else base_year5
        )
    else:
        selected_year5 = (
            float(selected_rows["yhat"].iloc[48:60].sum()) if not selected_rows.empty else base_year5
        )
    delta_year5 = selected_year5 - base_year5

    st.subheader("Data from SAC")
    refresh_status = st.session_state.pop("refresh_status", None)
    if refresh_status:
        if refresh_status["ok"] and refresh_status["refresh_used_cache"]:
            st.caption(f"Using cached data from {refresh_status['last_refresh']}.")
        elif refresh_status["ok"]:
            st.success("Refresh pipeline complete.")
        else:
            st.error("Refresh failed and cache missing. Run demo.refresh first.")

    if st.button("Refresh from SAC", use_container_width=True):
        with st.spinner("Running refresh → forecast → scenarios..."):
            result = run_all(cache_path=str(series_path))
        if result["ok"]:
            st.session_state["refresh_status"] = {
                "ok": True,
                "refresh_used_cache": result["refresh_used_cache"],
                "last_refresh": meta.last_refresh_time,
            }
        else:
            st.session_state["refresh_status"] = {"ok": False, "refresh_used_cache": False}
        st.rerun()
    with st.expander("SAC data details"):
        provider_name = meta_raw.get("provider_name", "unknown")
        metric_name = meta_raw.get("metric_name", "unknown")
        unit = meta_raw.get("unit", "unknown")
        output_mode = meta_raw.get("output_mode", "unknown")
        measure_used = meta_raw.get("measure_used", "unknown")
        aggregation = meta_raw.get("aggregation", "unknown")
        last_refresh = meta_raw.get("last_refresh_time", meta.last_refresh_time)
        filters_used = meta_raw.get("filters_used", {})
        st.markdown(
            f"""
            <div class="meta-grid">
              <div class="meta-key">Provider</div><div class="meta-val">{provider_name}</div>
              <div class="meta-key">Metric</div><div class="meta-val">{metric_name}</div>
              <div class="meta-key">Unit</div><div class="meta-val">{unit}</div>
              <div class="meta-key">Output</div><div class="meta-val">{output_mode}</div>
              <div class="meta-key">Currency</div><div class="meta-val">{currency or "unknown"}</div>
              <div class="meta-key">Measure</div><div class="meta-val">{measure_used}</div>
              <div class="meta-key">Aggregation</div><div class="meta-val">{aggregation}</div>
              <div class="meta-key">Filters</div><div class="meta-val">{json.dumps(filters_used)}</div>
              <div class="meta-key">Last refresh</div><div class="meta-val">{last_refresh}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with st.expander("Show 10 sample rows"):
        st.dataframe(series_df.head(10), use_container_width=True)

    st.subheader("Scenarios")
    # V3 presets (primary)
    alpha, beta = calibrate_alpha_beta(DEFAULT_ASSUMPTIONS.t0_cost, DEFAULT_ASSUMPTIONS.t0_fte, DEFAULT_ASSUMPTIONS.fixed_cost_share)
    ctx = DriverContext(alpha=alpha, beta0=beta)
    v3_names = list(PRESETS_V3.keys())
    v3_cols = st.columns(len(v3_names))
    for idx, name in enumerate(v3_names):
        preset: PresetV3 = PRESETS_V3[name]
        params = preset.params
        with v3_cols[idx]:
            if st.button(name.replace("_", " ").title(), use_container_width=True, key=f"v3preset_{name}"):
                scenario_df = apply_scenario_v3_simple(
                    forecast[["date", "yhat"]],
                    params,
                    context=ctx,
                )
                st.session_state["assistant_v3_overlay"] = scenario_df
                st.session_state["assistant_v3_label"] = f"Preset V3: {name.replace('_', ' ').title()}"
                if name == "reduce_cost_10pct" and params.fte_cut_plan:
                    st.session_state["assistant_v3_fte_plan"] = params.fte_cut_plan
                else:
                    st.session_state.pop("assistant_v3_fte_plan", None)
                st.success(f"Applied preset: {name.replace('_', ' ').title()}")
            st.caption(preset.description)
            st.caption(f"Year-1 delta vs base: {preset.expected_year1_delta_range[0]*100:+.1f}% to {preset.expected_year1_delta_range[1]*100:+.1f}%")
            if preset.steady_state_note:
                st.caption(preset.steady_state_note)
            if preset.implied_fte_cut:
                st.caption(f"Implied FTE cut: {preset.implied_fte_cut:.0f}")

    fte_plan = st.session_state.get("assistant_v3_fte_plan")
    if fte_plan:
        st.markdown("**Cost target plan (FTE cuts by seniority)**")
        plan_rows = [{"Seniority": k, "Cut FTE": v} for k, v in fte_plan.items()]
        st.table(pd.DataFrame(plan_rows))

    forecast_years = list(forecast["date"].dt.year.unique())
    preset_params, preset_warnings = validate_params(
        PRESETS_V2[selected_preset]["params"], horizon_years=len(forecast_years)
    )

    if "pending_override" in st.session_state:
        pending = st.session_state.pop("pending_override")
        st.session_state["override_defaults"] = pending
        st.session_state["growth_delta_pct_widget"] = float(pending["growth_delta_pct"])
        st.session_state["shock_pct_widget"] = float(pending["shock_pct"])
        st.session_state["drift_pct_widget"] = float(pending["drift_pct"])
        st.session_state["shock_duration_widget"] = int(pending["shock_duration"])
        st.session_state["shock_year_choice_widget"] = pending["shock_year_choice"]

    if "override_defaults" not in st.session_state:
        st.session_state["override_defaults"] = {
            "growth_delta_pct": float(preset_params.growth_delta_pp_per_year) * 100.0,
            "shock_pct": float(preset_params.shock_pct),
            "drift_pct": float(preset_params.drift_pp_per_year) * 100.0,
            "shock_duration": int(preset_params.shock_duration_months or 0),
            "shock_year_choice": str(preset_params.shock_start_year)
            if preset_params.shock_start_year
            else "(none)",
        }
    else:
        defaults = st.session_state["override_defaults"]
        if "growth_delta_pct" not in defaults:
            defaults["growth_delta_pct"] = float(defaults.get("growth_delta_pp", 0.0)) * 100.0
        if "drift_pct" not in defaults:
            defaults["drift_pct"] = float(defaults.get("drift_pp", 0.0)) * 100.0

    defaults = st.session_state["override_defaults"]
    current_growth_delta_pct = float(
        st.session_state.get("growth_delta_pct_widget", defaults["growth_delta_pct"])
    )
    current_shock_pct = float(st.session_state.get("shock_pct_widget", defaults["shock_pct"]))
    current_drift_pct = float(st.session_state.get("drift_pct_widget", defaults["drift_pct"]))
    current_shock_duration = int(
        st.session_state.get("shock_duration_widget", defaults["shock_duration"])
    )
    current_shock_year_choice = st.session_state.get(
        "shock_year_choice_widget", defaults["shock_year_choice"]
    )

    shock_year = None if current_shock_year_choice == "(none)" else int(current_shock_year_choice)
    growth_delta_pp = current_growth_delta_pct / 100.0
    drift_pp = current_drift_pct / 100.0
    override_error = None
    try:
        validate_overrides(
            forecast_years=forecast_years,
            shock_year=shock_year,
            shock_pct=current_shock_pct,
            growth_delta_pp=growth_delta_pp,
        )
    except ValueError as exc:
        override_error = str(exc)
        shock_year = None

    override_params = ScenarioParamsV2(
        growth_delta_pp_per_year=growth_delta_pp,
        shock_start_year=shock_year,
        shock_pct=current_shock_pct,
        shock_duration_months=current_shock_duration or None,
        drift_pp_per_year=drift_pp,
    )
    override_params, override_warnings = validate_params(
        override_params, horizon_years=len(forecast_years)
    )
    scenario_override = apply_scenario_v2(forecast[["date", "yhat"]], override_params, "override")

    # KPI prep (prefer V3 overlay, else preset, else custom override, else baseline)
    alpha_default, beta_default = calibrate_alpha_beta(
        DEFAULT_ASSUMPTIONS.t0_cost, DEFAULT_ASSUMPTIONS.t0_fte, DEFAULT_ASSUMPTIONS.fixed_cost_share
    )
    base_for_kpi = forecast.sort_values("date").reset_index(drop=True)
    scenario_for_kpi = None
    scenario_label_for_kpi = "Baseline forecast"

    v3_overlay = st.session_state.get("assistant_v3_overlay")
    if v3_overlay is not None:
        scenario_for_kpi = v3_overlay.copy()
        scenario_for_kpi["date"] = pd.to_datetime(scenario_for_kpi["date"])
        scenario_label_for_kpi = st.session_state.get("assistant_v3_label", "Preset/Assistant (V3)")
    elif selected_preset != "base" and not selected_rows.empty:
        scenario_for_kpi = selected_rows.copy()
        scenario_for_kpi["date"] = pd.to_datetime(scenario_for_kpi["date"])
        scenario_label_for_kpi = f"Preset: {selected_preset.replace('_', ' ').title()}"
    elif any(
        [
            override_params.growth_delta_pp_per_year,
            override_params.shock_start_year,
            override_params.shock_pct,
            override_params.shock_duration_months,
            override_params.drift_pp_per_year,
        ]
    ):
        scenario_for_kpi = scenario_override.copy()
        scenario_for_kpi["date"] = pd.to_datetime(scenario_for_kpi["date"])
        scenario_label_for_kpi = "Custom override"

    def _value_at_month(df: pd.DataFrame | None, month_idx: int) -> float | None:
        if df is None or df.empty:
            return None
        idx = min(month_idx, len(df) - 1)
        return float(df["yhat"].iloc[idx])

    base_t0 = float(base_for_kpi["yhat"].iloc[0])
    scen_t0 = _value_at_month(scenario_for_kpi, 0) or base_t0
    base_y1 = _value_at_month(base_for_kpi, 11) or base_t0
    scen_y1 = _value_at_month(scenario_for_kpi, 11) or base_y1
    base_y5 = _value_at_month(base_for_kpi, 59) or base_y1
    scen_y5 = _value_at_month(scenario_for_kpi, 59) or base_y5
    base_y10 = _value_at_month(base_for_kpi, 119) or base_y5
    scen_y10 = _value_at_month(scenario_for_kpi, 119) or base_y10

    def _pct_delta(base: float, scen: float) -> float:
        return scen / base - 1.0 if base else 0.0

    fte_base = _implied_fte(base_t0, alpha_default, beta_default)
    fte_scen = _implied_fte(scen_t0, alpha_default, beta_default)
    fte_delta = fte_scen - fte_base

    st.divider()
    st.subheader("Key KPIs")
    value_suffix = f" {unit_label}".rstrip()
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric(
        "t0 cost",
        f"{scen_t0:,.0f}{value_suffix}",
        delta=f"{scen_t0 - base_t0:,.0f} vs base",
    )
    k2.metric(
        "Year‑1",
        f"{scen_y1:,.0f}{value_suffix}",
        delta=f"{_pct_delta(base_y1, scen_y1)*100:+.1f}%",
    )
    k3.metric(
        "Year‑5",
        f"{scen_y5:,.0f}{value_suffix}",
        delta=f"{_pct_delta(base_y5, scen_y5)*100:+.1f}%",
    )
    k4.metric(
        "Year‑10",
        f"{scen_y10:,.0f}{value_suffix}",
        delta=f"{_pct_delta(base_y10, scen_y10)*100:+.1f}%",
    )
    k5.metric(
        "Implied FTE",
        f"{fte_scen:,.0f}",
        delta=f"{fte_delta:+.0f} vs base",
    )
    st.caption(f"Scenario shown: {scenario_label_for_kpi}")

    with st.container():
        st.caption("Assumptions (fixed for demo)")
        a1, a2, a3, a4 = st.columns(4)
        a1.metric("Baseline growth", f"{BASELINE_GROWTH_YOY*100:.1f}%/yr")
        a2.metric("Inflation (beta drift)", f"{BASELINE_INFLATION_PPY*100:.1f}%/yr")
        a3.metric("Fixed cost share", "20% (alpha≈2.0M)")
        a4.metric("t0 FTE", f"{DEFAULT_ASSUMPTIONS.t0_fte:,.0f} (implied {fte_base:,.0f})")

    st.subheader("Forecast view")
    chart_frames = []
    actual_plot = series_df[["date", "value"]].rename(columns={"value": "y"})
    actual_plot["series"] = "Actuals"
    chart_frames.append(actual_plot)

    baseline_plot = forecast[["date", "yhat"]].rename(columns={"yhat": "y"})
    baseline_plot["series"] = "Baseline forecast"
    chart_frames.append(baseline_plot)

    show_preset = selected_preset != "base" and not selected_rows.empty and v3_overlay is None
    preset_label = f"Preset: {selected_preset.replace('_', ' ').title()}"
    if show_preset:
        preset_plot = selected_rows[["date", "yhat"]].rename(columns={"yhat": "y"})
        preset_plot["series"] = preset_label
        chart_frames.append(preset_plot)

    show_override = any(
        [
            override_params.growth_delta_pp_per_year,
            override_params.shock_start_year,
            override_params.shock_pct,
            override_params.shock_duration_months,
            override_params.drift_pp_per_year,
        ]
    )
    if show_override:
        scenario_override["date"] = pd.to_datetime(scenario_override["date"])
        override_plot = scenario_override[["date", "yhat"]].rename(columns={"yhat": "y"})
        override_plot["series"] = "Custom override"
        chart_frames.append(override_plot)

    if v3_overlay is not None:
        v3_plot = v3_overlay.copy()
        v3_plot["date"] = pd.to_datetime(v3_plot["date"])
        v3_plot = v3_plot.rename(columns={"yhat": "y"})
        v3_plot["series"] = st.session_state.get("assistant_v3_label", "Preset/Assistant (V3)")
        chart_frames.append(v3_plot)

    chart_df = pd.concat(chart_frames, ignore_index=True)
    series_colors = {
        "Actuals": "#1f77b4",
        "Baseline forecast": "#c14b2a",
    }
    if show_preset:
        series_colors[preset_label] = "#6b6b6b"
    if show_override:
        series_colors["Custom override"] = "#2a7f62"
    if v3_overlay is not None:
        series_colors[st.session_state.get("assistant_v3_label", "AI Assistant (V3)")] = "#f2b134"
    series_order = list(series_colors.keys())
    color_scale = alt.Scale(domain=series_order, range=[series_colors[name] for name in series_order])

    y_title = metric_label if not title_unit else f"{metric_label} ({title_unit})"
    base_chart = alt.Chart(chart_df).mark_line().encode(
        x=alt.X("date:T", axis=alt.Axis(format="%Y-%m")),
        y=alt.Y("y:Q", title=y_title),
        color=alt.Color("series:N", scale=color_scale, legend=alt.Legend(title="Series")),
        tooltip=["series:N", "date:T", "y:Q"],
    )
    boundary = alt.Chart(pd.DataFrame({"date": [last_actual_date]})).mark_rule(
        color="#5a4d44",
        strokeDash=[4, 4],
    ).encode(x="date:T")
    st.altair_chart(base_chart + boundary, use_container_width=True)

    with st.expander("Legacy V2 forecasts"):
        st.subheader("Scenario Presets (V2 - legacy)")
        preset_names = list(PRESETS_V2.keys())
        preset_cols = st.columns(len(preset_names))
        for idx, name in enumerate(preset_names):
            preset = PRESETS_V2[name]
            with preset_cols[idx]:
                if st.button(name.replace("_", " ").title(), use_container_width=True, key=f"preset_v2_{name}"):
                    st.session_state["selected_preset_v2"] = name
                st.caption(preset["description"])
                st.caption(
                    f"Shock {preset['params'].shock_pct:+.2f} in {preset['params'].shock_start_year or '-'} "
                    f"for {preset['params'].shock_duration_months or 0}m · "
                    f"Growth {preset['params'].growth_delta_pp_per_year:+.2f} pp/yr · "
                    f"Drift {preset['params'].drift_pp_per_year:+.2f} pp/yr"
                )

        if preset_warnings:
            st.warning("Preset adjusted: " + " | ".join(preset_warnings))

        with st.expander("Scenario Overrides (optional)"):
            with st.form("override_form"):
                growth_delta_pct = st.slider(
                    "Growth delta (% per year)",
                    -50.0,
                    50.0,
                    float(defaults["growth_delta_pct"]),
                    1.0,
                    key="growth_delta_pct_widget",
                )
                year_options = ["(none)"] + [str(year) for year in forecast_years]
                default_year_choice = defaults["shock_year_choice"]
                if default_year_choice not in year_options:
                    default_year_choice = "(none)"
                shock_year_choice = st.selectbox(
                    "Shock year (optional)",
                    year_options,
                    index=year_options.index(default_year_choice),
                    key="shock_year_choice_widget",
                )
                shock_pct = st.slider(
                    "Shock pct (fraction, -0.25 = -25%)",
                    -0.9,
                    1.0,
                    float(defaults["shock_pct"]),
                    0.01,
                    key="shock_pct_widget",
                )
                drift_pct = st.slider(
                    "Drift (% per year)",
                    -20.0,
                    20.0,
                    float(defaults["drift_pct"]),
                    1.0,
                    key="drift_pct_widget",
                )
                shock_duration = st.slider(
                    "Shock duration (months, 0 = permanent)",
                    0,
                    60,
                    int(defaults["shock_duration"]),
                    1,
                    key="shock_duration_widget",
                )
                submitted = st.form_submit_button("Apply overrides")

            if submitted:
                st.session_state["override_defaults"] = {
                    "growth_delta_pct": growth_delta_pct,
                    "shock_pct": shock_pct,
                    "drift_pct": drift_pct,
                    "shock_duration": shock_duration,
                    "shock_year_choice": shock_year_choice,
                }
        if override_error:
            st.warning(override_error)
        if override_warnings:
            st.warning("Adjusted to stay within safe bounds: " + " | ".join(override_warnings))

        st.divider()
        st.subheader("Scenario Assistant (V2)")
        assistant_text = st.text_area("Describe a scenario", placeholder="e.g., trade wars is over")
        if st.button("Suggest parameters"):
            stats = summarize_series(series_df)
            suggestion = suggest_scenario(
                assistant_text,
                horizon_years=len(forecast_years),
                baseline_stats=stats,
                use_llm=True,
            )
            st.session_state["assistant_suggestion"] = suggestion

        suggestion = st.session_state.get("assistant_suggestion")
        if suggestion:
            mode = suggestion.get("mode", "llm")
            model = suggestion.get("llm_model")
            label = f"**Mode:** {mode}"
            if mode == "llm" and model:
                label += f" (model: {model})"
            st.markdown(label)
            if mode == "llm_error":
                st.error(f"LLM error: {_safe_error_text(suggestion.get('error'))}")
                raw_excerpt = suggestion.get("llm_raw_excerpt")
                if raw_excerpt and st.checkbox("Show raw LLM excerpt", value=False, key="llm_raw_excerpt_checkbox"):
                    st.code(raw_excerpt)
                if st.checkbox("Debug LLM payload", value=False):
                    llm_request = suggestion.get("llm_request", {})
                    if llm_request:
                        st.markdown("**LLM request**")
                        st.code(json.dumps(llm_request, indent=2), language="json")
                return
            rationale = suggestion.get("rationale", {})
            warnings = suggestion.get("warnings", [])
            if warnings:
                st.warning(" | ".join(warnings))
            with st.container():
                st.markdown("**Executive summary**")
                st.write(rationale.get("summary", ""))
                drivers = rationale.get("drivers", [])
                assumptions = rationale.get("assumptions", [])
                if drivers:
                    st.markdown("Drivers")
                    for item in drivers:
                        st.markdown(f"- {item}")
                if assumptions:
                    st.markdown("Assumptions")
                    for item in assumptions:
                        st.markdown(f"- {item}")
                st.caption(f"Confidence: {rationale.get('confidence', 'medium')}")

            s = suggestion["params"]
            st.markdown(
                f"""
                Suggested parameters:
                - growth delta: {s["growth_delta_pp_per_year"] * 100:+.1f}%/yr
                - shock start year: {s["shock_start_year"] or "n/a"}
                - shock pct (fraction): {s["shock_pct"]:+.2f}
                - shock duration: {s["shock_duration_months"]} months
                - drift: {s["drift_pp_per_year"] * 100:+.1f}%/yr
                """
            )

            preview_params = ScenarioParamsV2(
                growth_delta_pp_per_year=float(s["growth_delta_pp_per_year"]),
                shock_start_year=s["shock_start_year"],
                shock_pct=float(s["shock_pct"]),
                shock_duration_months=s["shock_duration_months"],
                drift_pp_per_year=float(s["drift_pp_per_year"]),
            )
            preview = _impact_preview(forecast, preview_params)
            if preview:
                st.markdown("**Impact preview (vs baseline)**")
                for offset, delta, pct in preview:
                    st.markdown(f"- Year {offset}: {delta:+,.0f} ({pct:+.1%})")
            if st.checkbox("Debug LLM payload", value=False):
                llm_request = suggestion.get("llm_request", {})
                if llm_request:
                    st.markdown("**LLM request**")
                    st.code(json.dumps(llm_request, indent=2), language="json")
                st.markdown("**LLM response**")
                st.code(json.dumps({"params": s, "rationale": rationale}, indent=2), language="json")
            def _apply_suggestion() -> None:
                s = st.session_state["assistant_suggestion"]["params"]
                st.session_state["pending_override"] = {
                    "growth_delta_pct": float(s["growth_delta_pp_per_year"]) * 100.0,
                    "shock_pct": float(s["shock_pct"]),
                    "drift_pct": float(s["drift_pp_per_year"]) * 100.0,
                    "shock_duration": int(s["shock_duration_months"] or 0),
                    "shock_year_choice": str(s["shock_start_year"]) if s["shock_start_year"] else "(none)",
                }
                if s.get("preset_base"):
                    st.session_state["pending_preset"] = _normalize_preset_name(s["preset_base"])

            st.button("Apply suggestion", on_click=_apply_suggestion, key="apply_v2_suggestion_btn")

    st.divider()
    st.subheader("AI Scenario Assistant (V3)")
    st.caption("Uses new HR presets and driver model; legacy V2 controls remain below.")
    assistant_v3_text = st.text_area("Describe a scenario (V3)", key="assistant_v3_text", placeholder="e.g., inflation shock that fades over a year")
    suggested_driver = st.session_state.get("assistant_v3_suggested_driver", "cost") or "cost"
    driver_options = ["cost", "fte", "cost_target"]
    driver_index = driver_options.index(suggested_driver) if suggested_driver in driver_options else 0
    driver_choice = st.selectbox("Scenario driver (UI wins; FTE is implied from cost)", driver_options, index=driver_index, key="assistant_v3_driver_widget")

    if st.button("Get suggestion (V3)"):
        stats = summarize_series(series_df)
        try:
            llm_result = request_suggestion(assistant_v3_text, horizon_years=len(forecast_years), baseline_stats=stats)
            suggestion_raw = llm_result["response"]
        except LLMError as exc:
            st.error(f"LLM error: {_safe_error_text(exc)}")
            raw_excerpt = None
        else:
            suggestion = suggestion_raw
            if isinstance(suggestion, str):
                try:
                    suggestion = parse_suggestion(suggestion)
                except Exception as exc:
                    st.error(f"Failed to parse suggestion: {_safe_error_text(exc)}")
                    suggestion = None
            if not suggestion or not isinstance(suggestion, dict) or "params" not in suggestion:
                st.error("Invalid suggestion payload.")
            else:
                st.session_state["assistant_v3_payload"] = {
                    "suggestion": suggestion,
                    "usage": llm_result.get("usage"),
                    "raw_excerpt": llm_result.get("raw_excerpt"),
                }
                st.session_state["assistant_v3_suggested_driver"] = suggestion.get("suggested_driver") or driver_choice
                try:
                    params_v3, validation_warnings = validate_and_prepare_params(suggestion.get("params", {}))
                except SuggestionValidationError as exc:
                    st.error(f"Validation failed: {_safe_error_text(exc)}")
                    clear_pending_v3()
                else:
                    ctx = build_driver_context(observed_t0_cost=last_actual_value, assumptions=DEFAULT_ASSUMPTIONS)
                    set_pending_v3(
                        params=params_v3,
                        driver_choice=driver_choice,
                        ctx=ctx,
                        rationale=suggestion.get("rationale", {}) or {},
                        warnings=validation_warnings,
                        safety=suggestion.get("safety"),
                        raw_suggestion=suggestion,
                        label=f"AI Assistant (V3) [{driver_choice}]",
                    )
                    st.success("Suggestion ready. Review below and click Apply to overlay.")

    pending_v3 = get_pending_v3()
    if pending_v3:
        ctx = pending_v3["ctx"]
        rationale = pending_v3.get("rationale", {})
        safety = pending_v3.get("safety", {}) or {}
        warnings = pending_v3.get("warnings", [])

        st.caption(f"Suggested driver: {pending_v3['raw_suggestion'].get('suggested_driver') or 'cost'} | You chose: {pending_v3['driver_choice']} (UI wins)")
        if ctx.warning:
            st.warning(ctx.warning)
        if warnings:
            st.warning("Adjusted to safe bounds: " + " | ".join(warnings))
        safety_warnings = safety.get("warnings") or []
        if safety_warnings:
            st.warning("LLM safety: " + " | ".join(safety_warnings))
        safety_adjustments = safety.get("adjustments") or []
        if safety_adjustments:
            st.info("Adjustments: " + " | ".join(safety_adjustments))

        alpha_col, beta_col, fshare_col = st.columns(3)
        alpha_col.metric("t0 cost used", f"{ctx.t0_cost_used:,.0f} EUR")
        beta_col.metric("Beta (per FTE)", f"{ctx.beta:,.0f}")
        fshare_col.metric("Alpha (fixed)", f"{ctx.alpha:,.0f}")
        st.caption("Implied FTE (derived) = max(0, (cost - alpha) / beta)")

        st.markdown("**Parameters**")
        st.table(_scenario_params_table(pending_v3["params"]))

        st.markdown("**Rationale**")
        title = rationale.get("title") or "Scenario rationale"
        st.markdown(f"**{title}**")
        st.write(rationale.get("summary", ""))
        why = rationale.get("why_these_numbers", [])
        assumptions = rationale.get("assumptions", [])
        sanity = rationale.get("sanity_checks", {})
        if why:
            st.markdown("Why these numbers")
            for item in why:
                st.markdown(f"- {item}")
        if assumptions:
            st.markdown("Assumptions")
            for item in assumptions:
                st.markdown(f"- {item}")
        if sanity:
            st.caption(
                f"Sanity check: ~{sanity.get('ten_year_multiplier_estimate', '')}x over 10y; {sanity.get('notes', '')}"
            )

        with st.form("apply_suggestion_v3_form"):
            apply_clicked = st.form_submit_button("Apply suggestion (V3)", use_container_width=True)
        if apply_clicked:
            scenario_df = apply_driver_scenario(
                forecast_cost_df=forecast[["date", "yhat"]],
                params=pending_v3["params"],
                driver=pending_v3["driver_choice"],
                ctx=ctx,
                scenario_name="assistant_v3",
            )
            st.session_state["assistant_v3_overlay"] = scenario_df
            st.session_state["assistant_v3_label"] = pending_v3.get("label", f"AI Assistant (V3) [{pending_v3['driver_choice']}]")
            clear_pending_v3()
            st.success("Applied V3 suggestion. Overlay updated.")
            st.rerun()

if __name__ == "__main__":
    main()
