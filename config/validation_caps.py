from __future__ import annotations

from config.core import VALIDATION_CAPS


_SEVERITY_CAPS = {
    "operational": {
        "cost_cagr_min": -0.20,
        "cost_cagr_max": 0.30,
        "fte_cagr_min": -0.25,
        "fte_cagr_max": 0.25,
        "baseline_dev_warn_low": 0.5,
        "baseline_dev_warn_high": 2.0,
        "mom_cap_default": 0.5,
        "mom_cap_shock": 0.8,
    },
    "stress": {
        "cost_cagr_min": -0.30,
        "cost_cagr_max": 0.40,
        "fte_cagr_min": -0.35,
        "fte_cagr_max": 0.35,
        "baseline_dev_warn_low": 0.4,
        "baseline_dev_warn_high": 2.5,
        "mom_cap_default": 0.6,
        "mom_cap_shock": 0.9,
    },
    "crisis": {
        "cost_cagr_min": -0.50,
        "cost_cagr_max": 0.60,
        "fte_cagr_min": -0.50,
        "fte_cagr_max": 0.50,
        "baseline_dev_warn_low": 0.3,
        "baseline_dev_warn_high": 3.0,
        "mom_cap_default": 0.7,
        "mom_cap_shock": 0.95,
    },
}


def caps_for_severity(severity: str) -> dict:
    severity_key = (severity or "").lower()
    caps = _SEVERITY_CAPS.get(severity_key, _SEVERITY_CAPS["operational"])
    merged = dict(VALIDATION_CAPS)
    merged.update(caps)
    return merged
