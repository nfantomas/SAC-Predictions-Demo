import pytest

from scenarios.profile import profile_factor


def test_profile_factor_step_and_zero_duration():
    assert profile_factor("step", 0, 0) == 1.0
    assert profile_factor("step", 3, 12) == 1.0


def test_profile_factor_linear_durations():
    assert profile_factor("linear", 0, 1) == pytest.approx(1.0)
    factors = [profile_factor("linear", i, 12) for i in range(12)]
    assert factors[0] == pytest.approx(1.0 / 12.0)
    assert factors[-1] == pytest.approx(1.0)
    assert factors == sorted(factors)


def test_profile_factor_exp_durations():
    assert profile_factor("exp", 0, 1) == pytest.approx(1.0)
    factors = [profile_factor("exp", i, 12) for i in range(12)]
    assert all(0.0 <= f <= 1.0 for f in factors)
    assert factors == sorted(factors)
    assert factors[-1] == pytest.approx(1.0)


def test_profile_factor_rejects_invalid_inputs():
    with pytest.raises(ValueError):
        profile_factor("linear", -1, 3)
    with pytest.raises(ValueError):
        profile_factor("linear", 0, -1)
    with pytest.raises(ValueError):
        profile_factor("weird", 0, 1)  # type: ignore[arg-type]
