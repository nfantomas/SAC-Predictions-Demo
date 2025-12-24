from pipeline.cache import CacheError, load_cache

from demo.refresh import refresh_from_sac
from pipeline.forecast_runner import run_forecast


def main() -> int:
    try:
        output, _ = refresh_from_sac("data/cache/sac_export.csv")
        print(f"REFRESH OK {output}")
    except Exception as exc:
        try:
            load_cache(data_path="data/cache/sac_export.csv")
        except CacheError:
            print(
                "Refresh failed and cache missing. "
                "Run `python -m demo.refresh --source sac` first."
            )
            return 1
        print(f"WARNING: Refresh failed; using cached data. ({exc})")

    try:
        result = run_forecast()
    except CacheError as exc:
        print(str(exc))
        return 1

    print(
        "FORECAST OK "
        f"horizon={result['horizon_months']} "
        f"output={result['output_path']} "
        f"meta={result['meta_path']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
