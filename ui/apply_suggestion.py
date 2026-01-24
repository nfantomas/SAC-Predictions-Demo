from __future__ import annotations

from typing import Any, Dict, Optional

import streamlit as st

from scenarios.schema import ScenarioParamsV3


def set_pending_v3(
    params: ScenarioParamsV3,
    driver_choice: str,
    ctx: Any,
    rationale: Dict[str, object] | None,
    warnings: list[str] | None = None,
    safety: Dict[str, object] | None = None,
    raw_suggestion: Dict[str, object] | None = None,
    label: Optional[str] = None,
    derived: Dict[str, object] | None = None,
) -> None:
    st.session_state["pending_v3"] = {
        "params": params,
        "driver_choice": driver_choice,
        "ctx": ctx,
        "rationale": rationale or {},
        "warnings": warnings or [],
        "safety": safety or {},
        "raw_suggestion": raw_suggestion or {},
        "label": label or "AI Assistant (V3)",
        "derived": derived or {},
    }


def get_pending_v3() -> Optional[Dict[str, object]]:
    return st.session_state.get("pending_v3")


def clear_pending_v3() -> None:
    st.session_state.pop("pending_v3", None)
