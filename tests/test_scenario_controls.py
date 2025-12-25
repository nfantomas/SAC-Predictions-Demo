import pytest

from ui.scenario_controls import validate_overrides


def test_validate_shock_year_in_range():
    with pytest.raises(ValueError):
        validate_overrides([2024, 2025], shock_year=2026, shock_pct=0.0, growth_delta_pp=0.0)


def test_validate_shock_pct_range():
    with pytest.raises(ValueError):
        validate_overrides([2024], shock_year=2024, shock_pct=-0.95, growth_delta_pp=0.0)
    with pytest.raises(ValueError):
        validate_overrides([2024], shock_year=2024, shock_pct=1.1, growth_delta_pp=0.0)


def test_validate_growth_delta_range():
    with pytest.raises(ValueError):
        validate_overrides([2024], shock_year=2024, shock_pct=0.0, growth_delta_pp=-0.6)
    with pytest.raises(ValueError):
        validate_overrides([2024], shock_year=2024, shock_pct=0.0, growth_delta_pp=0.6)
