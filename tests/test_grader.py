from __future__ import annotations

from evals.grader import grade_answer


def _model_answer() -> dict:
    return {
        "summary_text": "Costs rise moderately; hiring volume eases.",
        "applied_params": {"driver": "cost", "beta_multiplier": 1.05},
        "key_metrics": {"driver": "cost", "warnings_count": 1},
    }


def test_grade_score_is_bounded_int():
    def fake_llm(_system: str, _user: str):
        return {
            "score": 3,
            "reasoning": "Strong answer. Driver and math are aligned.",
            "tags": ["driver_selection", "clarity"],
            "suggested_fix": ["Keep assumptions concise."],
        }

    grade = grade_answer(
        question="If salary rises 5%, what happens to costs?",
        expected_answer="Use cost driver and quantify variable cost lift.",
        model_answer=_model_answer(),
        llm_call=fake_llm,
    )
    assert isinstance(grade["score"], int)
    assert 0 <= grade["score"] <= 3
    assert grade["tags"]


def test_grade_repairs_json_fence_response():
    def fake_llm(_system: str, _user: str):
        return """```json
{"score": 2, "reasoning": "Mostly correct.", "tags": ["clarity"], "suggested_fix": ["Quantify assumptions."]}
```"""

    grade = grade_answer(
        question="keep FTE flat and reduce costs 5%",
        expected_answer="Cost lever only with flat FTE constraint.",
        model_answer=_model_answer(),
        llm_call=fake_llm,
    )
    assert grade["score"] == 2
    assert grade["tags"] == ["clarity"]


def test_grade_retries_then_returns_json():
    calls = {"count": 0}

    def fake_llm(_system: str, _user: str):
        calls["count"] += 1
        if calls["count"] == 1:
            return "this is not json"
        return {
            "score": 1,
            "reasoning": "Directionally right but misses key assumptions.",
            "tags": ["missing_assumptions", "clarity"],
            "suggested_fix": ["State baseline assumptions explicitly."],
        }

    grade = grade_answer(
        question="attrition increases from 10% to 18%",
        expected_answer="FTE and cost impact over two years with assumptions.",
        model_answer=_model_answer(),
        llm_call=fake_llm,
    )
    assert calls["count"] >= 2
    assert grade["score"] == 1
    assert "missing_assumptions" in grade["tags"]

