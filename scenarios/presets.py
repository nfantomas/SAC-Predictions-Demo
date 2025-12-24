from scenarios.overlay import ScenarioParams


PRESETS = {
    "base": {
        "description": "Baseline forecast with no scenario adjustments.",
        "params": ScenarioParams(),
        "story": "Keep baseline assumptions unchanged.",
    },
    "downside_trade_war": {
        "description": "Permanent shock plus slower growth.",
        "params": ScenarioParams(growth_delta_pp=-0.01, shock_year=2027, shock_pct=-0.08),
        "story": "Trade-war style shock with a lasting step-down and slower growth.",
    },
    "upside": {
        "description": "Improved growth outlook.",
        "params": ScenarioParams(growth_delta_pp=0.01),
        "story": "Higher growth due to favorable macro conditions.",
    },
    "aging_drift": {
        "description": "Gradual negative drift in growth.",
        "params": ScenarioParams(drift_pp_per_year=-0.02),
        "story": "Aging workforce slowly reduces growth over time.",
    },
}
