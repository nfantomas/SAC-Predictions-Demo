import pandas as pd
import pytest

from model.cost_driver import calibrate_alpha_beta, cost_from_fte, project_beta


def test_calibrate_alpha_beta_defaults():
    alpha, beta = calibrate_alpha_beta(10_000_000, 800, 0.20)
    assert alpha == 2_000_000
    assert beta == 10_000


def test_project_beta_inflates():
    betas = project_beta(10_000, inflation_ppy=0.03, months=12)
    assert len(betas) == 12
    assert betas.iloc[-1] > betas.iloc[0]


def test_cost_from_fte_floor_alpha():
    alpha, beta = 2_000_000, 10_000
    betas = pd.Series([beta] * 3)
    fte = pd.Series([800, 0, -100])
    costs = cost_from_fte(alpha, betas, fte)
    assert (costs >= alpha).all()
    with pytest.raises(ValueError):
        cost_from_fte(alpha, betas, pd.Series([1, 2]))
