from pipeline.run_all import run_all


def main() -> int:
    result = run_all()
    if not result["ok"]:
        print(
            "Refresh failed and cache missing. "
            "Run `python -m demo.refresh --source sac` first."
        )
        return 1
    if result["refresh_used_cache"]:
        print("WARNING: Refresh failed; using cached data.")
    print(
        "FORECAST OK "
        f"horizon={result['forecast']['horizon_months']} "
        f"output={result['forecast']['output_path']} "
        f"meta={result['forecast']['meta_path']}"
    )
    print(
        "SCENARIOS OK "
        f"count={result['scenarios']['scenario_count']} "
        f"output={result['scenarios']['output_path']} "
        f"meta={result['scenarios']['meta_path']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
