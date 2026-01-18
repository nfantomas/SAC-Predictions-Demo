import pandas as pd
import pytest

from pipeline.normalize_timeseries import NormalizeError, NormalizeSpec, normalize_timeseries


def test_parse_yyyymm_and_aggregate():
    df = pd.DataFrame(
        {
            "Date": ["202001", "202001", "202002"],
            "SignedData": [1, 2.5, 3],
        }
    )
    result = normalize_timeseries(df)
    assert list(result["date"]) == ["2020-01-01", "2020-02-01"]
    assert list(result["value"]) == [3.5, 3.0]


def test_reject_invalid_date():
    df = pd.DataFrame({"Date": ["20201"], "SignedData": [1]})
    with pytest.raises(NormalizeError):
        normalize_timeseries(df)


def test_allow_non_numeric_and_drop():
    df = pd.DataFrame(
        {
            "Date": ["202001", "202001", "202002"],
            "SignedData": ["10", "bad", None],
        }
    )
    result = normalize_timeseries(
        df,
        spec=NormalizeSpec(allow_non_numeric=True),
    )
    assert list(result["value"]) == [10.0]
