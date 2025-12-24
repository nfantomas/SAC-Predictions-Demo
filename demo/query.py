import statistics

from pipeline.cache import CacheError, load_cache


def _parse_float(value: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid numeric value: {value}") from exc


def main() -> int:
    try:
        rows, meta = load_cache(data_path="data/cache/sac_export.csv")
    except CacheError as exc:
        print(str(exc))
        return 1

    if not rows:
        print("Cache is empty. Run demo.refresh first.")
        return 1

    dates = [row["date"] for row in rows]
    values = [_parse_float(row["value"]) for row in rows]
    row_count = len(rows)
    min_date = min(dates)
    max_date = max(dates)

    print(f"Rows: {row_count}")
    print(f"Min date: {min_date}")
    print(f"Max date: {max_date}")
    print(f"Mean: {statistics.mean(values):.4f}")
    print(f"Median: {statistics.median(values):.4f}")
    print(f"Missing values: {sum(1 for v in values if v is None)}")

    print("First 3 rows:")
    for row in rows[:3]:
        print(row)

    print("Last 3 rows:")
    for row in rows[-3:]:
        print(row)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
