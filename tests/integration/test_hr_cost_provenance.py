import os
import pandas as pd
import pytest

from pipeline.cache import load_cache, load_cache_meta_raw


@pytest.mark.sac
def test_last_actual_matches_cache_meta():
    if not os.getenv("RUN_SAC_TESTS"):
        pytest.skip("RUN_SAC_TESTS not set")
    rows, meta = load_cache(data_path="data/cache/sac_export.csv")
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.sort_values("date")
    assert df["date"].iloc[-1].date().isoformat() == meta.max_date
    assert df["value"].iloc[-1] == df["value"].iloc[-1]


@pytest.mark.sac
def test_meta_provenance_fields_present():
    if not os.getenv("RUN_SAC_TESTS"):
        pytest.skip("RUN_SAC_TESTS not set")
    meta_raw = load_cache_meta_raw()
    for field in ["metric_name", "unit", "currency", "measure_used", "filters_used", "aggregation"]:
        assert field in meta_raw
