from scenarios.fte_planner import FteCutPlan, plan_fte_cuts


def test_plan_fte_cuts_basic():
    plan = plan_fte_cuts(
        cost_target_pct=-0.10,
        alpha=2_000_000,
        beta=10_000,
        baseline_fte=800,
        baseline_cost=10_000_000,
    )
    assert isinstance(plan, FteCutPlan)
    assert plan.total_fte_delta == -100
    cuts = plan.cuts_by_seniority
    assert round(cuts["Junior"] + cuts["Mid"] + cuts["Senior"], 5) == -100


def test_cuts_do_not_exceed_category_headcount():
    plan = plan_fte_cuts(
        cost_target_pct=-0.50,
        alpha=2_000_000,
        beta=10_000,
        baseline_fte=10,
        baseline_cost=10_000_000,
    )
    for name, cut in plan.cuts_by_seniority.items():
        assert cut >= -5  # no category exceeds its share
