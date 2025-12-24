from pipeline.cache import CacheError, load_cache
from pipeline.forecast_runner import run_forecast


def main() -> int:
    try:
        rows, meta = load_cache(data_path="data/cache/sac_export.csv")
    except CacheError as exc:
        print(str(exc))
        return 1
    row_count = len(rows)
    print(f"Input rows: {row_count}")
    print(f"Input min date: {meta.min_date}")
    print(f"Input max date: {meta.max_date}")

    try:
        result = run_forecast()
    except CacheError as exc:
        print(str(exc))
        return 1

    print(
        "Forecast OK "
        f"horizon={result['horizon_months']} "
        f"output={result['output_path']} "
        f"meta={result['meta_path']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
