import types

import pytest
import streamlit as st

from scenarios.schema import ScenarioParamsV3
from ui.apply_suggestion import clear_pending_v3, get_pending_v3, set_pending_v3


@pytest.fixture(autouse=True)
def _reset_session(monkeypatch):
    monkeypatch.setattr(st, "session_state", {})
    yield
    monkeypatch.setattr(st, "session_state", {})


def test_set_and_clear_pending_v3():
    params = ScenarioParamsV3()
    ctx = types.SimpleNamespace(alpha=1, beta=1, t0_cost_used=1)

    set_pending_v3(params, "cost", ctx, rationale={"title": "r"}, warnings=["w"])
    pending = get_pending_v3()
    assert pending
    assert pending["params"] == params
    assert pending["driver_choice"] == "cost"
    assert pending["warnings"] == ["w"]

    clear_pending_v3()
    assert get_pending_v3() is None
