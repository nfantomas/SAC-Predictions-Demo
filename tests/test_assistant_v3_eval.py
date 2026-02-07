import csv
from pathlib import Path

import pytest

from evals.assistant_v3_eval import build_scorecard, load_eval_cases, run_eval_case, select_eval_cases


def _write_case_csv(path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "id",
                "question",
                "expected_driver",
                "expected_answer_summary",
                "expected_params_json",
                "assumptions_to_mention",
                "must_include_checks",
            ],
        )
        w.writeheader()
        w.writerow(
            {
                "id": "QX",
                "question": "reduce workforce by 10%",
                "expected_driver": "fte",
                "expected_answer_summary": "workforce reduction and costs",
                "expected_params_json": '{"fte_delta_pct": -0.1, "lag_months": 3}',
                "assumptions_to_mention": "fixed vs variable cost",
                "must_include_checks": "non-negative cost",
            }
        )


def test_load_eval_cases_parses_expected_fields(tmp_path: Path):
    path = tmp_path / "cases.csv"
    _write_case_csv(path)

    cases = load_eval_cases(path)
    assert len(cases) == 1
    case = cases[0]
    assert case.case_id == "QX"
    assert case.expected_driver == "fte"
    assert case.expected_params["fte_delta_pct"] == -0.1


def test_run_eval_case_with_mock_suggestion(tmp_path: Path):
    path = tmp_path / "cases.csv"
    _write_case_csv(path)
    case = load_eval_cases(path)[0]

    def fake_suggestion(question: str, horizon_years: int, baseline_stats: dict):
        assert "workforce" in question
        assert horizon_years == 10
        assert "last_value" in baseline_stats
        return {
            "response": {
                "scenario_driver": "fte",
                "params": {
                    "lag_months": 3,
                    "onset_duration_months": 6,
                    "event_duration_months": None,
                    "recovery_duration_months": None,
                    "shape": "linear",
                    "impact_mode": "level",
                    "impact_magnitude": 0.0,
                    "growth_delta_pp_per_year": 0.0,
                    "drift_pp_per_year": 0.0,
                    "fte_delta_pct": -0.1,
                },
                "rationale": {
                    "title": "Workforce reduction",
                    "summary": "Costs decrease due to lower FTE.",
                    "assumptions": ["fixed vs variable cost split"],
                    "why_these_numbers": ["Non-negative cost path"],
                },
                "safety": {"warnings": ["Bounds checked"]},
            }
        }

    result = run_eval_case(case, suggestion_fn=fake_suggestion)
    assert result.error is None
    assert result.driver_match is True
    assert result.param_sign_matches >= 1
    assert result.summary_keyword_coverage > 0
    assert result.assumptions_keyword_coverage > 0
    assert result.answer_text
    assert result.latency_ms >= 0


def test_select_eval_cases_by_id(tmp_path: Path):
    path = tmp_path / "cases.csv"
    _write_case_csv(path)
    cases = load_eval_cases(path)
    selected = select_eval_cases(cases, ["QX"])
    assert len(selected) == 1
    assert selected[0].case_id == "QX"


def test_select_eval_cases_raises_on_unknown_id(tmp_path: Path):
    path = tmp_path / "cases.csv"
    _write_case_csv(path)
    cases = load_eval_cases(path)
    with pytest.raises(ValueError):
        select_eval_cases(cases, ["Q999"])


def test_build_scorecard_has_summary_and_question_scores(tmp_path: Path):
    path = tmp_path / "cases.csv"
    _write_case_csv(path)
    case = load_eval_cases(path)[0]

    def fake_suggestion(question: str, horizon_years: int, baseline_stats: dict):
        return {
            "response": {
                "scenario_driver": "fte",
                "params": {
                    "driver": "fte",
                    "lag_months": 3,
                    "onset_duration_months": 6,
                    "event_duration_months": None,
                    "recovery_duration_months": None,
                    "shape": "linear",
                    "impact_mode": "level",
                    "impact_magnitude": 0.0,
                    "growth_delta_pp_per_year": 0.0,
                    "drift_pp_per_year": 0.0,
                    "fte_delta_pct": -0.1,
                },
                "rationale": {
                    "title": "Workforce reduction",
                    "summary": "Costs decrease due to lower FTE.",
                    "assumptions": ["fixed vs variable cost split"],
                    "why_these_numbers": ["Non-negative cost path"],
                },
                "safety": {"warnings": []},
            }
        }

    result = run_eval_case(case, suggestion_fn=fake_suggestion)
    scorecard = build_scorecard([result])
    assert scorecard["summary"]["total_questions"] == 1
    assert scorecard["summary"]["total_matches"] == 1
    assert scorecard["questions"][0]["answer_score"] in (1, 2, 3)
