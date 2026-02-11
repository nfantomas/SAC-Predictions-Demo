from __future__ import annotations

from typing import Any, Dict

from evals.generate_answer import generate_answer


def _suggestion_payload(driver: str = "cost_target") -> Dict[str, Any]:
    return {
        "scenario_driver": "auto",
        "suggested_driver": driver,
        "driver_rationale": "test",
        "params": {
            "driver": driver,
            "lag_months": 0,
            "onset_duration_months": 3,
            "event_duration_months": None,
            "recovery_duration_months": None,
            "shape": "linear",
            "impact_mode": "level",
            "impact_magnitude": 0.0,
            "growth_delta_pp_per_year": 0.0,
            "drift_pp_per_year": 0.0,
            "event_growth_delta_pp_per_year": None,
            "event_growth_exp_multiplier": None,
            "post_event_growth_pp_per_year": None,
            "fte_delta_abs": None,
            "fte_delta_pct": None,
            "beta_multiplier": None,
            "cost_target_pct": -0.1 if driver == "cost_target" else None,
        },
        "rationale": {
            "title": "Test",
            "summary": "Test summary",
            "assumptions": [],
            "why_these_numbers": [],
            "sanity_checks": {"ten_year_multiplier_estimate": 0.9, "notes": "ok"},
        },
        "safety": {"adjustments": [], "warnings": []},
    }


def test_generate_answer_returns_required_keys(monkeypatch):
    monkeypatch.setattr(
        "evals.generate_answer.request_suggestion",
        lambda question, horizon_years, baseline_stats: {"response": _suggestion_payload(), "provider": "x", "model": "y"},
    )
    out = generate_answer("keep costs flat")
    assert "model_output_json" in out
    assert "applied_params" in out
    assert "summary_text" in out
    assert "key_metrics" in out
    assert out["key_metrics"]["driver"] in ("cost", "fte", "cost_target")


def test_generate_answer_handles_parse_failure(monkeypatch):
    monkeypatch.setattr(
        "evals.generate_answer.request_suggestion",
        lambda question, horizon_years, baseline_stats: {"response": "```json\n{\"bad\":true}\n```"},
    )
    out = generate_answer("bad parse")
    assert out["error_type"] == "parse_error"
    assert out["applied_params"] == {}


def test_generate_answer_stable_driver_on_fixed_payload(monkeypatch):
    questions = [
        "keep costs flat",
        "reduce costs by 10%",
        "cap labor growth at 2%",
    ]
    monkeypatch.setattr(
        "evals.generate_answer.request_suggestion",
        lambda question, horizon_years, baseline_stats: {"response": _suggestion_payload("cost_target")},
    )
    drivers = [generate_answer(q)["key_metrics"]["driver"] for q in questions]
    assert drivers == ["cost_target", "cost_target", "cost_target"]
