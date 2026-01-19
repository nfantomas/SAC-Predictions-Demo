import pytest

from model.driver_model import compute_alpha_beta, cost_from_fte, fte_from_cost, resolve_t0_cost


def test_compute_alpha_beta_defaults_match_spec():
    alpha, beta = compute_alpha_beta(10_000_000, 0.20, 800)
    assert alpha == 2_000_000
    assert beta == 10_000


def test_resolve_t0_cost_prefers_observed_when_mismatch():
    chosen, warning = resolve_t0_cost(observed_t0_cost=6_000_000, configured_t0_cost=10_000_000, mismatch_threshold=0.20)
    assert chosen == 6_000_000
    assert warning


def test_resolve_t0_cost_keeps_config_when_within_threshold():
    chosen, warning = resolve_t0_cost(observed_t0_cost=10_500_000, configured_t0_cost=10_000_000, mismatch_threshold=0.20)
    assert chosen == 10_000_000
    assert warning is None


def test_cost_from_fte_and_fte_from_cost_behave_and_clamp():
    alpha, beta = compute_alpha_beta(10_000_000, 0.20, 800)
    cost = cost_from_fte(720, alpha, beta)
    assert cost == pytest.approx(alpha + 720 * beta)
    fte_target = fte_from_cost(9_000_000, alpha, beta)
    assert fte_target == pytest.approx(700)
    assert fte_from_cost(-1, alpha, beta) == 0.0


def test_compute_alpha_beta_rejects_invalid():
    with pytest.raises(ValueError):
        compute_alpha_beta(10_000_000, -0.1, 800)
    with pytest.raises(ValueError):
        compute_alpha_beta(10_000_000, 0.5, 0)

