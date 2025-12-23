import csv
from pathlib import Path

from sac_connector.export import normalize_rows


def test_fixture_normalizes_and_has_required_fields():
    fixture_path = Path("tests/fixtures/sample_series.csv")
    rows = []
    with fixture_path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)

    normalized = normalize_rows(
        rows,
        date_field="date",
        value_field="value",
        dim_fields=["dim_region"],
        grain="month",
    )

    assert normalized
    for row in normalized:
        assert row["date"]
        assert row["value"] is not None
