from llm.validation_result import summarize_warnings


def test_summarize_warnings_dedups_and_caps():
    summary, details = summarize_warnings(
        warnings=["A", "B", "A", "C", "D", "E", "F"],
        clamps=["C", "G", "G"],
        normalizations=["N1", "N1"],
        max_items=5,
    )
    assert len(summary) == 5
    assert len(details) >= len(summary)
    assert len(details) == len(set(details))
    assert "A" in details and "G" in details and "N1" in details
