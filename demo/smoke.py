import csv
from pathlib import Path

from pipeline.cache import build_meta, save_cache
from sac_connector.export import normalize_rows


def main() -> int:
    fixture_path = Path("tests/fixtures/sample_series.csv")
    if not fixture_path.exists():
        print("Fixture missing: tests/fixtures/sample_series.csv")
        return 1

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
    meta = build_meta(normalized, source="fixture")
    save_cache(normalized, meta, data_path="data/cache/fixture.csv")
    print("SMOKE OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
