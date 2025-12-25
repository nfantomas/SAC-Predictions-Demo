from __future__ import annotations

import os
from typing import Dict, List, Optional

import numpy as np
import pandas as pd


class NarrativeError(Exception):
    pass


def summarize_series(series_df: pd.DataFrame) -> Dict[str, float]:
    if series_df.empty:
        raise NarrativeError("Series is empty.")
    if "date" not in series_df.columns or "value" not in series_df.columns:
        raise NarrativeError("Series must include date and value columns.")
    values = pd.to_numeric(series_df["value"], errors="coerce")
    if values.isna().all():
        raise NarrativeError("Series values are invalid.")
    last_value = float(values.iloc[-1])
    if len(values) >= 12:
        recent = values.iloc[-12:]
        trend = float(recent.iloc[-1] - recent.iloc[0])
    else:
        trend = float(values.iloc[-1] - values.iloc[0])
    volatility = float(values.pct_change().abs().replace([np.inf, -np.inf], np.nan).mean(skipna=True) or 0.0)
    return {
        "last_value": last_value,
        "trend_12m": trend,
        "volatility": volatility,
    }


def generate_narrative(
    stats: Dict[str, float],
    scenario_params: Dict[str, Optional[float]],
    market_indications_text: str,
    use_llm: bool = False,
) -> Dict[str, object]:
    if use_llm:
        llm_key = os.getenv("NARRATIVE_LLM_KEY")
        if not llm_key:
            return {
                "mode": "template",
                "title": "Baseline outlook (template fallback)",
                "summary": "LLM unavailable; using deterministic template output.",
                "bullets": [
                    f"Last value: {stats.get('last_value', 0):.2f}",
                    f"12m trend: {stats.get('trend_12m', 0):+.2f}",
                    f"Volatility proxy: {stats.get('volatility', 0):.3f}",
                ],
                "assumptions": "LLM key missing or unavailable; template mode enforced.",
                "reason": "missing_llm_key",
            }
        return {
            "mode": "template",
            "title": "Baseline outlook (template fallback)",
            "summary": "LLM integration not configured; using template output.",
            "bullets": [
                f"Last value: {stats.get('last_value', 0):.2f}",
                f"12m trend: {stats.get('trend_12m', 0):+.2f}",
                f"Volatility proxy: {stats.get('volatility', 0):.3f}",
            ],
            "assumptions": "LLM not enabled in this demo.",
            "reason": "llm_unavailable",
        }

    bullets: List[str] = [
        f"Last observed HR cost: {stats.get('last_value', 0):,.2f}.",
        f"12‑month change: {stats.get('trend_12m', 0):+.2f}.",
        f"Volatility proxy: {stats.get('volatility', 0):.3f}.",
    ]
    if scenario_params:
        bullets.append(
            "Scenario params: "
            f"growth {scenario_params.get('growth_delta_pp_per_year', 0):+.2f} pp/yr, "
            f"shock {scenario_params.get('shock_pct', 0):+.2f} from "
            f"{scenario_params.get('shock_start_year', 'n/a')} "
            f"for {scenario_params.get('shock_duration_months', 'n/a')} months, "
            f"drift {scenario_params.get('drift_pp_per_year', 0):+.2f} pp/yr."
        )
    if market_indications_text:
        bullets.append(f"Market notes: {market_indications_text.strip()}")

    summary = "Baseline HR cost forecast reflects recent trends with scenario adjustments applied."
    assumptions = "Template narrative; no external model calls."
    return {
        "mode": "template",
        "title": "HR Cost Outlook",
        "summary": summary,
        "bullets": bullets,
        "assumptions": assumptions,
    }
