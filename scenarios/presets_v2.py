from scenarios.overlay_v2 import ScenarioParamsV2


PRESETS_V2 = {
    "base": {
        "description": "Baseline with no adjustments.",
        "params": ScenarioParamsV2(),
        "story": "Baseline HR cost outlook.",
    },
    "trade_war_downside": {
        "description": "Shock -8% in 2027 for 12m; growth -3 pp/yr.",
        "params": ScenarioParamsV2(
            growth_delta_pp_per_year=-0.03,
            shock_start_year=2027,
            shock_pct=-0.08,
            shock_duration_months=12,
        ),
        "story": "Trade-war shock with a temporary step-down and slower growth.",
    },
    "growth_upside": {
        "description": "Growth +3 pp/yr.",
        "params": ScenarioParamsV2(growth_delta_pp_per_year=0.03),
        "story": "Higher growth due to expansion and hiring.",
    },
    "aging_pressure": {
        "description": "Drift -2 pp/yr.",
        "params": ScenarioParamsV2(drift_pp_per_year=-0.02),
        "story": "Aging workforce slowly reduces growth over time.",
    },
}
