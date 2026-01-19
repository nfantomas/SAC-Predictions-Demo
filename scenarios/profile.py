from __future__ import annotations

import math

from scenarios.schema import Shape


def profile_factor(shape: Shape, month_index: int, duration_months: int) -> float:
    """
    Normalized factor in [0, 1] for ramp-in/ramp-out profiles.
    - duration_months == 0 behaves like a step (immediate full impact).
    - month_index is zero-based within the onset or recovery window.
    """
    if shape not in ("step", "linear", "exp"):
        raise ValueError("Invalid shape; expected step, linear, or exp.")
    if duration_months < 0:
        raise ValueError("duration_months must be >= 0.")
    if month_index < 0:
        raise ValueError("month_index must be >= 0.")

    if duration_months == 0 or shape == "step":
        return 1.0

    progress = min(1.0, (month_index + 1) / float(duration_months))
    if progress >= 1.0:
        return 1.0
    if shape == "linear":
        return progress
    if shape == "exp":
        eased = 1.0 - math.exp(-4 * progress)
        return min(1.0, eased)

    raise ValueError("Invalid shape; expected step, linear, or exp.")
