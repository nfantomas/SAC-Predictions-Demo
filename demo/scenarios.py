from pipeline.cache import CacheError
from pipeline.scenario_runner import run_scenarios


def main() -> int:
    try:
        result = run_scenarios()
    except CacheError as exc:
        print(str(exc))
        return 1

    print(
        "Scenarios OK "
        f"count={result['scenario_count']} "
        f"output={result['output_path']} "
        f"meta={result['meta_path']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
