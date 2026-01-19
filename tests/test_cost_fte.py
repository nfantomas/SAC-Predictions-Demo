import pytest

from models.cost_fte import compute_alpha_beta, cost_from_fte, fte_from_cost


def test_compute_alpha_beta_defaults():
    alpha, beta = compute_alpha_beta(10_000_000, 0.20, 800)
    assert alpha == 2_000_000
    assert beta == 10_000


def test_cost_reduction_implies_fte_cut():
    alpha, beta = compute_alpha_beta(10_000_000, 0.20, 800)
    target_cost = 9_000_000
    target_fte = fte_from_cost(target_cost, alpha, beta)
    assert target_fte == pytest.approx(700)
    cost_back = cost_from_fte(target_fte, alpha, beta)
    assert cost_back == pytest.approx(target_cost)


def test_invalid_inputs_rejected():
    with pytest.raises(ValueError):
        compute_alpha_beta(10_000_000, -0.1, 800)
    with pytest.raises(ValueError):
        fte_from_cost(1_000_000, alpha=1_000_000, beta=0)
