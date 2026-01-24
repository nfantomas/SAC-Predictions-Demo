from __future__ import annotations

import json
from pathlib import Path

import altair as alt

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    HAS_PLOTLY = True
except ImportError:  # pragma: no cover - optional dependency
    HAS_PLOTLY = False
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
from scenarios.presets_v3 import PRESETS_V3, PresetV3
from scenarios.schema import ScenarioParamsV3
from scenarios.validate_v3 import validate_projection
from scenarios.v3 import DriverContext, apply_scenario_v3_simple
from ui.apply_suggestion import clear_pending_v3, get_pending_v3, set_pending_v3
from ui.assistant_v3_pipeline import apply_driver_scenario, build_driver_context, parse_suggestion, resolve_driver_and_params

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


def _impact_preview(*args, **kwargs):
    return []


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
    df = pd.DataFrame([data]).T.reset_index().rename(columns={"index": "param", 0: "value"})
    df["value"] = df["value"].apply(lambda v: "" if v is None else str(v))
    return df


def _quarterly_cost_and_fte(df: pd.DataFrame, label: str, alpha: float, beta: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Aggregate a monthly cost series into quarterly totals and end-of-quarter FTE (implied).
    Cost = sum within quarter; FTE = last month of quarter.
    """
    if df.empty:
        return pd.DataFrame(columns=["quarter", "cost", "series"]), pd.DataFrame(columns=["quarter", "fte", "series"])
    tmp = df.copy()
    tmp["date"] = pd.to_datetime(tmp["date"])
    tmp = tmp.sort_values("date")
    period = tmp["date"].dt.to_period("Q")
    tmp["quarter"] = period.dt.start_time
    tmp["quarter_label"] = period.apply(lambda p: f"Q{p.quarter} {p.year}")
    tmp["quarter_order"] = period.apply(lambda p: p.year * 4 + p.quarter)
    tmp["fte"] = tmp["y"].apply(lambda c: _implied_fte(float(c), alpha, beta))
    cost_q = (
        tmp.groupby(["quarter", "quarter_label", "quarter_order"], as_index=False)["y"]
        .sum()
        .rename(columns={"y": "cost"})
    )
    cost_q["series"] = label
    fte_q = (
        tmp.groupby(["quarter", "quarter_label", "quarter_order"])
        .tail(1)[["quarter", "quarter_label", "quarter_order", "fte"]]
        .rename(columns={"fte": "fte"})
    )
    fte_q["series"] = label
    return cost_q, fte_q


def _inject_styles() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;600&family=IBM+Plex+Serif:wght@500;700&display=swap');
        :root {
          --bg: #f7f9fc;
          --card: #ffffff;
          --primary: #009fe3;
          --primary-dark: #004c93;
          --secondary: #8c1d82;
          --ink: #0a0a0a;
          --muted: #adadad;
          --border: #d9e1ec;
        }
        .stApp {
          background: linear-gradient(135deg, rgba(0,159,227,0.10), rgba(0,76,147,0.08)), var(--bg);
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
          border: 1px solid var(--border);
          border-radius: 14px;
          padding: 1rem 1.2rem;
          box-shadow: 0 8px 24px rgba(0,0,0,0.06);
        }
        .meta-grid {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 0.5rem 1rem;
          font-size: 0.95rem;
        }
        .meta-key { color: var(--primary-dark); font-weight: 600; }
        .meta-val { color: var(--ink); }
        .stButton>button, .stDownloadButton>button {
          background-color: var(--primary);
          color: #ffffff;
          border: 1px solid var(--primary-dark);
          border-radius: 10px;
        }
        .stButton>button:hover {
          background-color: var(--primary-dark);
          border-color: var(--primary-dark);
        }
        .stTabs [data-baseweb="tab"] { color: var(--primary-dark); }
        .stTabs [data-baseweb="tab-list"] { border-bottom: 1px solid var(--border); }
        .stMetricValue { color: var(--primary-dark) !important; }
        .stCaption, .stMarkdown { color: var(--ink); }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_app() -> None:
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
        f'<div class="app-title">HR Cost & Workforce Forecast</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        f"Data from SAP Analytics Cloud (SAC). Last refresh: {meta.last_refresh_time}. Scenarios modify baseline assumptions."
    )
    series_df = pd.DataFrame(rows)
    series_df["date"] = pd.to_datetime(series_df["date"])
    series_df["value"] = pd.to_numeric(series_df["value"], errors="coerce")
    series_df = series_df.sort_values("date")

    with st.expander("Data provenance", expanded=False):
        provider_name = meta_raw.get("provider_name", "unknown")
        dataset_name = meta_raw.get("metric_name", "unknown")
        filters_used = meta_raw.get("filters_used", {})
        st.markdown(
            f"""
            • Provider: **{provider_name or 'unknown'}** (masked)<br>
            • Dataset: **{dataset_name}**<br>
            • Rows: **{len(series_df):,}** | Date range: **{series_df['date'].min().date()} → {series_df['date'].max().date()}**<br>
            • Filters: **{filters_used}**<br>
            • Status: <span style="color:#00b050">● Connected</span>
            """,
            unsafe_allow_html=True,
        )

    last_actual_value = float(series_df["value"].iloc[-1])
    last_actual_date = series_df["date"].iloc[-1]
    use_average = _is_headcount(metric_name, unit)
    if use_average:
        next_12_value = float(forecast["yhat"].iloc[:12].mean())
        year10_value = float(forecast["yhat"].iloc[-12:].mean())
    else:
        next_12_value = float(forecast["yhat"].iloc[:12].sum())
        year10_value = float(forecast["yhat"].iloc[-12:].sum())

    delta_year5 = 0.0

    forecast_years = list(forecast["date"].dt.year.unique())

    # KPI prep (prefer V3 overlay; else baseline)
    alpha_default, beta_default = calibrate_alpha_beta(
        DEFAULT_ASSUMPTIONS.t0_cost, DEFAULT_ASSUMPTIONS.t0_fte, DEFAULT_ASSUMPTIONS.fixed_cost_share
    )
    base_for_kpi = forecast.sort_values("date").reset_index(drop=True)
    scenario_for_kpi = None
    scenario_label_for_kpi = "Plan / Baseline forecast"

    v3_overlay = st.session_state.get("assistant_v3_overlay")
    if v3_overlay is not None:
        scenario_for_kpi = v3_overlay.copy()
        scenario_for_kpi["date"] = pd.to_datetime(scenario_for_kpi["date"])
        scenario_label_for_kpi = st.session_state.get("assistant_v3_label", "Preset/Assistant (V3)")

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

    def _fmt_millions(value: float) -> str:
        return f"{value/1_000_000:,.2f}M EUR"

    def _delta_badge(text: str, positive: bool) -> str:
        color = "#00b050" if positive else "#c0392b"
        return f'<span style="background:{color};color:white;padding:4px 8px;border-radius:12px;font-size:0.8rem;">{text}</span>'

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.markdown(f"**Current month cost**<br><span style='font-size:1.2rem'>{_fmt_millions(scen_t0)}</span><br>{_delta_badge(f'{scen_t0 - base_t0:,.0f} vs base', scen_t0>=base_t0)}", unsafe_allow_html=True)
    k2.markdown(f"**Cost 12M**<br><span style='font-size:1.2rem'>{_fmt_millions(scen_y1)}</span><br>{_delta_badge(f'{_pct_delta(base_y1, scen_y1)*100:+.1f}%', scen_y1>=base_y1)}", unsafe_allow_html=True)
    k3.markdown(f"**Cost 5Y**<br><span style='font-size:1.2rem'>{_fmt_millions(scen_y5)}</span><br>{_delta_badge(f'{_pct_delta(base_y5, scen_y5)*100:+.1f}%', scen_y5>=base_y5)}", unsafe_allow_html=True)
    k4.markdown(f"**Cost 10Y**<br><span style='font-size:1.2rem'>{_fmt_millions(scen_y10)}</span><br>{_delta_badge(f'{_pct_delta(base_y10, scen_y10)*100:+.1f}%', scen_y10>=base_y10)}", unsafe_allow_html=True)
    k5.markdown(f"**FTE (estimated)**<br><span style='font-size:1.2rem'>{fte_scen:,.0f}</span><br>{_delta_badge(f'{fte_delta:+.0f} vs base', fte_delta>=0)}", unsafe_allow_html=True)
    st.caption(f"Scenario shown: {scenario_label_for_kpi}")

    with st.expander("Model assumptions"):
        st.markdown(
            f"""
            <div style="font-size:0.9rem;color:var(--ink);">
              • Baseline cost growth: <strong>{BASELINE_GROWTH_YOY*100:.1f}%/yr</strong><br>
              • Inflation on beta: <strong>{BASELINE_INFLATION_PPY*100:.1f}%/yr</strong><br>
              • Fixed cost share: <strong>20% (alpha≈2.0M)</strong><br>
              • t0 FTE: <strong>{DEFAULT_ASSUMPTIONS.t0_fte:,.0f}</strong> (implied {fte_base:,.0f})
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.subheader("Forecast view")
    st.caption("EUR/month; FTE shown as end-of-quarter estimates.")
    chart_frames = []
    actual_plot = series_df[["date", "value"]].rename(columns={"value": "y"})
    actual_plot["series"] = "Actual"
    chart_frames.append(actual_plot)

    baseline_plot = forecast[["date", "yhat"]].rename(columns={"yhat": "y"})
    baseline_plot["series"] = "Plan / Baseline forecast"
    chart_frames.append(baseline_plot)

    scenario_series_label = st.session_state.get("assistant_v3_label", "Scenario")
    if v3_overlay is not None:
        v3_plot = v3_overlay.copy()
        v3_plot["date"] = pd.to_datetime(v3_plot["date"])
        v3_plot = v3_plot.rename(columns={"yhat": "y"})
        v3_plot["series"] = scenario_series_label
        chart_frames.append(v3_plot)

    chart_df = pd.concat(chart_frames, ignore_index=True)
    series_colors = {
        "Actual": "#009fe3",  # primary
        "Plan / Baseline forecast": "#00b050",  # prediction green
    }
    if v3_overlay is not None:
        series_colors[scenario_series_label] = "#e67e22"  # scenario accent
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

    st.caption("Quarterly EUR totals with end-of-quarter FTE; initial view focuses on your selected years.")
    # Quarterly view: cost totals (bars) and end-of-quarter FTE (line)
    cost_quarterly_frames: list[pd.DataFrame] = []
    fte_quarterly_frames: list[pd.DataFrame] = []
    actual_cost_df = actual_plot.rename(columns={"y": "y"})
    cost_q, fte_q = _quarterly_cost_and_fte(actual_cost_df, "Actual", alpha_default, beta_default)
    cost_quarterly_frames.append(cost_q)
    fte_quarterly_frames.append(fte_q)

    base_q_cost, base_q_fte = _quarterly_cost_and_fte(baseline_plot, "Plan / Baseline forecast", alpha_default, beta_default)
    cost_quarterly_frames.append(base_q_cost)
    fte_quarterly_frames.append(base_q_fte)

    if v3_overlay is not None:
        overlay_df = v3_overlay.copy()
        overlay_df["date"] = pd.to_datetime(overlay_df["date"])
        overlay_df = overlay_df.rename(columns={"yhat": "y"})
        overlay_label = st.session_state.get("assistant_v3_label", "Scenario")
        overlay_cost_q, overlay_fte_q = _quarterly_cost_and_fte(overlay_df, overlay_label, alpha_default, beta_default)
        cost_quarterly_frames.append(overlay_cost_q)
        fte_quarterly_frames.append(overlay_fte_q)

    cost_quarterly_df = pd.concat(cost_quarterly_frames, ignore_index=True)
    fte_quarterly_df = pd.concat(fte_quarterly_frames, ignore_index=True)
    # Ensure datetime dtype for Plotly range handling
    cost_quarterly_df["quarter"] = pd.to_datetime(cost_quarterly_df["quarter"])
    fte_quarterly_df["quarter"] = pd.to_datetime(fte_quarterly_df["quarter"])

    # Derive quarter center positions using actual quarter length
    quarter_end = cost_quarterly_df["quarter"] + pd.offsets.QuarterEnd(0)
    quarter_len = (quarter_end - cost_quarterly_df["quarter"]).dt.days
    quarter_len_days = quarter_len.iloc[0] if not quarter_len.empty else 90
    half_q = pd.to_timedelta(quarter_len_days / 2, unit="D")
    cost_quarterly_df["quarter_center"] = cost_quarterly_df["quarter"] + half_q
    fte_quarterly_df["quarter_center"] = fte_quarterly_df["quarter"] + half_q

    cost_quarterly_df = cost_quarterly_df.sort_values("quarter_order")
    fte_quarterly_df = fte_quarterly_df.sort_values("quarter_order")
    x_enc = alt.X(
        "quarter_center:T",
        sort=cost_quarterly_df.groupby("quarter_label")["quarter_center"].first().tolist(),
        title="",
        axis=alt.Axis(format="%Y-Q%q"),
    )
    series_list = cost_quarterly_df["series"].unique().tolist()
    overlay_label = st.session_state.get("assistant_v3_label", "Scenario")
    color_map = {
        "Actual": "#009fe3",
        "Plan / Baseline forecast": "#00b050",  # prediction green
        overlay_label: "#66c47d",  # comparison green
    }
    # Offset FTE markers slightly per series so each sits above its own bar
    # Compute per-series x-offset so FTE markers sit centered on their own bar
    series_list_sorted = series_list
    base_offset = pd.Timedelta(days=quarter_len_days / (len(series_list_sorted) + 1))
    offsets = {
        s: pd.Timedelta(days=(idx - (len(series_list_sorted) - 1) / 2) * base_offset.days)
        for idx, s in enumerate(series_list_sorted)
    }
    fte_quarterly_df["quarter_pos"] = fte_quarterly_df.apply(
        lambda r: r["quarter_center"] + offsets.get(r["series"], pd.Timedelta(days=0)), axis=1
    )

    if not cost_quarterly_df.empty and HAS_PLOTLY:
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        for series in series_list:
            subset = cost_quarterly_df[cost_quarterly_df["series"] == series]
            fig.add_trace(
                go.Bar(
                    x=subset["quarter_center"],
                    y=subset["cost"],
                    name=f"{series} cost",
                    marker_color=color_map.get(series, None),
                    customdata=subset["quarter_label"],
                    hovertemplate="<b>%{customdata}</b><br>%{y:,.0f}",
                    text=None,
                    showlegend=True,
                ),
                secondary_y=False,
            )
        fte_series_list = fte_quarterly_df["series"].unique().tolist()
        for series in fte_series_list:
            subset = fte_quarterly_df[fte_quarterly_df["series"] == series]
            fig.add_trace(
                go.Scatter(
                    x=subset["quarter_pos"],
                    y=subset["fte"],
                    mode="lines+markers+text",
                    name=f"{series} FTE",
                    marker=dict(color=color_map.get(series, "#4c8f2f"), size=8),
                    line=dict(color=color_map.get(series, "#4c8f2f"), width=3),
                    text=[f"{v:,.0f}" for v in subset["fte"]],
                    textposition="top center",
                    hovertemplate="<b>%{text}</b><br>%{y:,.0f} FTE",
                    showlegend=True,
                ),
                secondary_y=True,
            )
        x_range = [
            pd.Timestamp("2027-01-01"),
            pd.Timestamp("2029-12-31"),
        ]
        tick_df = (
            cost_quarterly_df[["quarter_center", "quarter_label"]]
            .drop_duplicates()
            .sort_values("quarter_center")
        )
        fig.update_xaxes(
            title_text="",
            tickformat="%Y Q%q",
            range=x_range,
            autorange=False,
            tickmode="array",
            tickvals=tick_df["quarter_center"].tolist(),
            ticktext=tick_df["quarter_label"].tolist(),
            showgrid=True,
            gridcolor="#e6e6e6",
        )
        fig.update_layout(
            title="FTE & Cost per Quarter",
            barmode="group",
            bargap=0.2,
            height=430,
            legend=dict(orientation="h", yanchor="bottom", y=1.04, xanchor="right", x=1.0),
            xaxis=dict(
                rangeselector=dict(buttons=[]),
                rangeslider=dict(visible=True),
            ),
            plot_bgcolor="#ffffff",
            paper_bgcolor="#ffffff",
            margin=dict(t=40, l=10, r=10, b=50),
        )
        fig.update_yaxes(
            title_text="Quarterly cost",
            secondary_y=False,
            range=[0, 100_000_000],
            tickformat=",.0f",
            showgrid=True,
            gridcolor="#e6e6e6",
        )
        fig.update_yaxes(
            title_text="FTE (end of quarter)",
            secondary_y=True,
            tickformat=",.0f",
            showgrid=False,
        )
        st.plotly_chart(fig, use_container_width=True)
    elif not HAS_PLOTLY:
        st.warning("Plotly is not installed; showing limited Altair fallback. Install plotly>=5.22.0 for interactive zoom/pan.")
        # Altair fallback with brush selection (defaults to last actual + 2y)
        start_date = pd.to_datetime(last_actual_date)
        end_date = start_date + pd.DateOffset(years=2)
        brush = alt.selection_interval(encodings=["x"], init={"x": [start_date, end_date]})

        base_cost = (
            alt.Chart(cost_quarterly_df)
            .mark_bar(opacity=0.65)
            .encode(
                x=x_enc,
                y=alt.Y("cost:Q", title="Quarterly cost", scale=alt.Scale(domain=[0, 100_000_000])),
                color=alt.Color(
                    "series:N",
                    legend=alt.Legend(title="Series"),
                    scale=alt.Scale(
                        domain=series_list,
                        range=[color_map.get(s, "#adadad") for s in series_list],
                    ),
                ),
                tooltip=["series:N", alt.Tooltip("quarter:T", format="%Y-Q%q"), alt.Tooltip("cost:Q", format=",.0f")],
            )
        )
        cost_detail = base_cost.transform_filter(brush)
        fte_detail = (
            alt.Chart(fte_quarterly_df)
            .mark_line(point=True, strokeWidth=3)
            .encode(
                x=alt.X("quarter_pos:T", title="", axis=alt.Axis(format="%Y-Q%q")),
                y=alt.Y("fte:Q", title="FTE (end of quarter)", axis=alt.Axis(orient="right")),
                color=alt.Color(
                    "series:N",
                    legend=alt.Legend(title="Series"),
                    scale=alt.Scale(
                        domain=series_list,
                        range=[color_map.get(s, "#adadad") for s in series_list],
                    ),
                ),
                tooltip=["series:N", alt.Tooltip("quarter:T", format="%Y-Q%q"), alt.Tooltip("fte:Q", format=",.0f")],
            )
            .transform_filter(brush)
        )
        fte_text = (
            alt.Chart(fte_quarterly_df)
            .mark_text(dy=-12, fontSize=11, fontWeight="bold")
            .encode(
                x="quarter_pos:T",
                y="fte:Q",
                text=alt.Text("fte:Q", format=",.0f"),
                color=alt.Color(
                    "series:N",
                    legend=None,
                    scale=alt.Scale(
                        domain=series_list,
                        range=[color_map.get(s, "#adadad") for s in series_list],
                    ),
                ),
            )
            .transform_filter(brush)
        )
        detail_layer = (
            alt.layer(cost_detail, fte_detail, fte_text)
            .resolve_scale(y="independent")
            .properties(height=330, title="FTE & Cost per Quarter (Altair fallback)")
        )

        overview = (
            base_cost.encode(y=alt.Y("cost:Q", title="")).properties(height=80)
            .add_selection(brush)
        )
        st.altair_chart(detail_layer & overview, use_container_width=True)

    st.divider()
    st.subheader("What-if Scenarios")
    preset_keys = list(PRESETS_V3.keys())
    if not preset_keys:
        st.info("No presets available.")
    else:
        selected_key = st.session_state.get("selected_preset_v3", preset_keys[0])
        cols = st.columns(len(preset_keys))
        for idx, key in enumerate(preset_keys):
            preset = PRESETS_V3[key]
            label = preset.key.replace("_", " ").title()
            btn = cols[idx % len(cols)].button(label, key=f"preset_btn_{key}", use_container_width=True)
            cols[idx % len(cols)].caption(preset.description)
            if btn:
                selected_key = key
                st.session_state["selected_preset_v3"] = key
                ctx = DriverContext(alpha=alpha_default, beta0=beta_default)
                scenario_df = apply_scenario_v3_simple(
                    forecast[["date", "yhat"]],
                    preset.params,
                    context=ctx,
                    horizon_months=len(forecast),
                )
                st.session_state["assistant_v3_overlay"] = scenario_df
                st.session_state["assistant_v3_label"] = f"Scenario preset: {preset.key.replace('_', ' ').title()}"
                st.session_state["assistant_v3_suggested_driver"] = preset.params.driver or "cost"
                st.success(f"Applied {label}. Overlay updated.")
                st.rerun()
        if selected_key in PRESETS_V3:
            st.caption(PRESETS_V3[selected_key].story or PRESETS_V3[selected_key].description)
        if scenario_for_kpi is not None:
            delta_12m = _pct_delta(base_y1, scen_y1) * 100
            delta_5y = _pct_delta(base_y5, scen_y5) * 100
            with st.container():
                st.markdown(
                    f"""
                    <div class="card" style="margin-top:0.5rem;">
                      <strong>Scenario summary</strong><br>
                      • 12M impact: {delta_12m:+.1f}% vs plan<br>
                      • 5Y impact: {delta_5y:+.1f}% vs plan
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    st.divider()
    st.subheader("AI scenario assistant")
    st.caption("Uses new HR presets and driver model.")
    if st.button("Example: “Inflation spike mid next year”", key="example_prompt"):
        st.session_state["assistant_v3_text"] = "Inflation spike mid next year"
    assistant_v3_text = st.text_area("Describe a scenario (V3)", key="assistant_v3_text", placeholder="e.g., inflation shock that fades over a year")

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
                try:
                    ctx = build_driver_context(observed_t0_cost=last_actual_value, assumptions=DEFAULT_ASSUMPTIONS)
                    driver_used, params_v3, validation_warnings, derived = resolve_driver_and_params(
                        suggestion, ctx, override_driver=None, horizon_months=len(forecast)
                    )
                except SuggestionValidationError as exc:
                    st.error(f"Validation failed: {_safe_error_text(exc)}")
                    clear_pending_v3()
                else:
                    st.session_state["assistant_v3_suggested_driver"] = driver_used
                    set_pending_v3(
                        params=params_v3,
                        driver_choice=driver_used,
                        ctx=ctx,
                        rationale=suggestion.get("rationale", {}) or {},
                        warnings=validation_warnings,
                        safety=suggestion.get("safety"),
                        raw_suggestion=suggestion,
                        label=f"AI Assistant (V3) [{driver_used}]",
                        derived=derived,
                    )
                    st.success(f"Suggestion ready with driver: {driver_used}. Review below and click Apply to overlay.")

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

        with st.expander("Scenario parameters and rationale", expanded=False):
            st.markdown("**Parameters**")
            st.table(_scenario_params_table(pending_v3["params"]))

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

    st.divider()
    with st.expander("Advanced options"):
        st.subheader("Data from SAC")
        refresh_status = st.session_state.pop("refresh_status", None)
        if refresh_status:
            if refresh_status["ok"] and refresh_status["refresh_used_cache"]:
                st.caption(f"Using cached data from {refresh_status['last_refresh']}.")
            elif refresh_status["ok"]:
                st.success("Refresh pipeline complete.")
            else:
                st.error("Refresh failed and cache missing. Run demo.refresh first.")

        st.caption("Maintenance: refresh SAC cache (not needed for normal demo use).")
        if st.button("Maintenance: Refresh SAC cache", use_container_width=True):
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
        meta_raw_safe = {}
        try:
            meta_raw_safe = meta_raw
        except NameError:
            meta_raw_safe = {}

        with st.expander("SAC data details"):
            provider_name = meta_raw_safe.get("provider_name", "unknown")
            metric_name = meta_raw_safe.get("metric_name", "unknown")
            unit = meta_raw_safe.get("unit", "unknown")
            output_mode = meta_raw_safe.get("output_mode", "unknown")
            measure_used = meta_raw_safe.get("measure_used", "unknown")
            aggregation = meta_raw_safe.get("aggregation", "unknown")
            last_refresh = meta_raw_safe.get("last_refresh_time", meta.last_refresh_time)
            filters_used = meta_raw_safe.get("filters_used", {})
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

def main() -> None:
    try:
        _render_app()
    except Exception as exc:  # pragma: no cover - defensive guard for Streamlit runtime
        st.error("The app hit an unexpected error while loading. Please check logs or refresh.")
        st.exception(exc)
        raise


if __name__ == "__main__":
    main()
