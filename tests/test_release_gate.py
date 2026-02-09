from evals.release_gate import evaluate_release_gate


def _base_row(**overrides):
    row = {
        "id": "Q01",
        "question": "reduce costs by 10%",
        "applied_driver": "cost_target",
        "deterministic_ten_year_multiplier": 0.9,
        "warning_summary_count": 2,
        "hard_fail": False,
    }
    row.update(overrides)
    return row


def test_release_gate_passes_nominal():
    rows = [_base_row(run=i) for i in range(1, 4)]
    report = evaluate_release_gate(rows, min_apply_rate=0.9, min_driver_stability=0.6, max_multiplier_range=0.5)
    assert report["ok"] is True


def test_release_gate_fails_warning_cap():
    rows = [_base_row(warning_summary_count=6)]
    report = evaluate_release_gate(rows, min_apply_rate=0.9, min_driver_stability=0.6, max_multiplier_range=0.5)
    assert report["ok"] is False
    assert report["checks"]["warnings_ok"] is False


def test_release_gate_fails_non_shock_multiplier():
    rows = [_base_row(deterministic_ten_year_multiplier=4.2)]
    report = evaluate_release_gate(rows, min_apply_rate=0.9, min_driver_stability=0.6, max_multiplier_range=0.5)
    assert report["ok"] is False
    assert report["checks"]["multiplier_bounds_ok"] is False


def test_release_gate_allows_shock_higher_multiplier():
    rows = [_base_row(question="war scenario in europe", deterministic_ten_year_multiplier=6.0)]
    report = evaluate_release_gate(rows, min_apply_rate=0.9, min_driver_stability=0.6, max_multiplier_range=0.5, shock_max=8.0)
    assert report["ok"] is True

