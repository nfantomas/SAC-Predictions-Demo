import pandas as pd

from model.cost_driver import calibrate_alpha_beta
from scenarios.presets_v3 import PRESETS_V3
from scenarios.v3 import DriverContext, apply_scenario_v3_simple


def _baseline(months: int = 36, start_cost: float = 10_000_000.0, inflation_ppy: float = 0.03) -> pd.DataFrame:
    dates = pd.date_range(start="2028-01-01", periods=months, freq="MS")
    growth = (1.0 + inflation_ppy) ** (pd.RangeIndex(months) / 12.0)
    return pd.DataFrame({"date": dates.date.astype(str), "yhat": start_cost * growth})


def test_presets_year1_deltas_are_within_expected_ranges():
    base = _baseline()
    alpha, beta0 = calibrate_alpha_beta(10_000_000, 800, 0.2)
    ctx = DriverContext(alpha=alpha, beta0=beta0)

    for preset in PRESETS_V3.values():
        overlay = apply_scenario_v3_simple(base, preset.params, ctx)
        pct_delta_year1 = overlay["yhat"].iloc[11] / base["yhat"].iloc[11] - 1.0
        low, high = preset.expected_year1_delta_range
        assert low <= pct_delta_year1 <= high, f"{preset.key} outside expected range"


def test_hiring_freeze_growth_is_inflation_only():
    base = _baseline()
    alpha, beta0 = calibrate_alpha_beta(10_000_000, 800, 0.2)
    ctx = DriverContext(alpha=alpha, beta0=beta0)
    preset = PRESETS_V3["freeze_hiring"]
    overlay = apply_scenario_v3_simple(base, preset.params, ctx)
    # Year-1 delta should be negative vs 6% baseline but small (~-2 to -3%)
    pct_delta_year1 = overlay["yhat"].iloc[11] / base["yhat"].iloc[11] - 1.0
    assert -0.04 < pct_delta_year1 < -0.01
    # Slope remains upward (no collapse)
    assert list(overlay["yhat"]) == sorted(overlay["yhat"])
