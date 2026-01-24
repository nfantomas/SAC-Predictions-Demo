import json
from pathlib import Path

import pandas as pd

from demo.llm.safety_v3 import SafetyBounds, validate_sanity_v3
from llm.validate_v3 import ValidateContext, validate_and_sanitize
from scenarios.schema import ScenarioParamsV3


FIXTURES = [
    Path("demo/llm/fixtures/inflation_shock_mid_next_year.json"),
    Path("demo/llm/fixtures/reduce_costs_10pct.json"),
]


def _baseline(months: int = 120) -> pd.DataFrame:
    dates = pd.date_range("2028-01-01", periods=months, freq="MS")
    return pd.DataFrame({"date": dates, "yhat": [10_000_000] * months})


def test_fixture_parses_and_validates():
    for fixture in FIXTURES:
        payload = json.loads(fixture.read_text())
        assert payload.get("driver") in {"cost", "fte", "cost_target"}
        raw_params = payload["params"]
        params, warnings = validate_and_sanitize(raw_params, ctx=ValidateContext(horizon_months=120))
        assert isinstance(params, ScenarioParamsV3)
        ok, warn2, blocks = validate_sanity_v3(params, _baseline(), SafetyBounds())
        assert ok, f"Blocks for {fixture}: {blocks}"
        # allow warnings but ensure they are strings
        for w in warnings + warn2:
            assert isinstance(w, str)
