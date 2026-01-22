import numpy as np
import pandas as pd

from model.cost_driver import calibrate_alpha_beta
from scenarios.presets_v3 import PRESETS_V3
from scenarios.v3 import DriverContext, apply_scenario_v3_simple


def _baseline(months: int = 120, start_cost: float = 10_000_000.0, growth_ppy: float = 0.06) -> pd.DataFrame:
    dates = pd.date_range("2028-01-01", periods=months, freq="MS")
    growth = (1.0 + growth_ppy) ** (np.arange(months) / 12.0)
    return pd.DataFrame({"date": dates.date.astype(str), "yhat": start_cost * growth})


def _ctx():
    alpha, beta0 = calibrate_alpha_beta(10_000_000, 800, 0.2)
    return DriverContext(alpha=alpha, beta0=beta0)


def test_costs_never_negative_and_not_below_alpha():
    base = _baseline()
    ctx = _ctx()
    for preset in PRESETS_V3.values():
        overlay = apply_scenario_v3_simple(base, preset.params, ctx)
        assert (overlay["yhat"] >= ctx.alpha - 1e-6).all()


def test_year10_multiplier_within_bounds():
    base = _baseline()
    ctx = _ctx()
    for preset in PRESETS_V3.values():
        overlay = apply_scenario_v3_simple(base, preset.params, ctx)
        multiplier = overlay["yhat"].iloc[119] / base["yhat"].iloc[119]
        assert 0.3 <= multiplier <= 3.0


def test_freeze_hiring_slope_near_inflation_only():
    base = _baseline()
    ctx = _ctx()
    freeze = PRESETS_V3["freeze_hiring"]
    overlay = apply_scenario_v3_simple(base, freeze.params, ctx)
    y0 = overlay["yhat"].iloc[0]
    y12 = overlay["yhat"].iloc[11]
    yoy = (y12 / y0) - 1
    assert 0.02 <= yoy <= 0.04  # ~3% YoY
    assert list(overlay["yhat"]) == sorted(overlay["yhat"])


def test_inflation_shock_steps_at_t6():
    base = _baseline(months=24)
    ctx = _ctx()
    shock = PRESETS_V3["inflation_shock"]
    overlay = apply_scenario_v3_simple(base, shock.params, ctx)
    assert overlay["yhat"].iloc[5] == base["yhat"].iloc[5]
    assert overlay["yhat"].iloc[6] > base["yhat"].iloc[6]


def test_convert_contractors_returns_to_parallel_slope():
    base = _baseline(months=36)
    ctx = _ctx()
    preset = PRESETS_V3["convert_it_contractors"]
    overlay = apply_scenario_v3_simple(base, preset.params, ctx)
    assert overlay["yhat"].iloc[0] == base["yhat"].iloc[0]
    base_tail_delta = base["yhat"].iloc[35] - base["yhat"].iloc[23]
    over_tail_delta = overlay["yhat"].iloc[35] - overlay["yhat"].iloc[23]
    ratio = over_tail_delta / base_tail_delta if base_tail_delta else 1.0
    assert 0.85 <= ratio <= 1.05  # parallel slope after ramp (allow slight loss)
    # Dip should start after lag and during ramp (~month 1-24)
    assert overlay["yhat"].iloc[12] < overlay["yhat"].iloc[0]


def test_outsourcing_ramp_is_smooth():
    base = _baseline(months=24)
    ctx = _ctx()
    preset = PRESETS_V3["outsource_120_uk_cz"]
    overlay = apply_scenario_v3_simple(base, preset.params, ctx)
    first_segment = overlay["yhat"].iloc[:7].tolist()
    assert first_segment[0] <= base["yhat"].iloc[0]
    assert first_segment[-1] < first_segment[0]
    for prev, curr in zip(first_segment, first_segment[1:]):
        assert curr <= prev * 1.005


def test_reduce_cost_hits_target():
    base = _baseline(months=36)
    ctx = _ctx()
    preset = PRESETS_V3["reduce_cost_10pct"]
    overlay = apply_scenario_v3_simple(base, preset.params, ctx)
    target_ratio = overlay["yhat"].iloc[12] / base["yhat"].iloc[12]
    assert 0.89 <= target_ratio <= 0.91
