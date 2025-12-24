import argparse
import json
import os
from typing import Dict

from config import ConfigError, load_config
from pipeline.cache import CacheError, CacheMeta, build_meta, load_cache, save_cache
from pipeline.normalize_timeseries import NormalizeError, normalize_timeseries
from sac_connector.export import ExportError, export_all, normalize_rows
from sac_connector.timeseries import DEFAULT_SLICE, fetch_timeseries


def _parse_params(raw: str) -> Dict[str, str]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("SAC_EXPORT_PARAMS must be valid JSON.") from exc
    if not isinstance(data, dict):
        raise ValueError("SAC_EXPORT_PARAMS must be a JSON object.")
    return {str(k): str(v) for k, v in data.items()}


def refresh_from_sac(output_path: str) -> tuple[str, CacheMeta]:
    config = load_config()

    export_url = os.getenv("SAC_EXPORT_URL", "").strip()
    provider_id = os.getenv("SAC_PROVIDER_ID", "").strip()
    namespace_id = os.getenv("SAC_NAMESPACE_ID", "sac").strip() or "sac"

    params = _parse_params(os.getenv("SAC_EXPORT_PARAMS", ""))
    date_field = os.getenv("SAC_DATE_FIELD", "date")
    value_field = os.getenv("SAC_VALUE_FIELD", "value")
    dim_fields_raw = os.getenv("SAC_DIM_FIELDS", "")
    dim_fields = [dim.strip() for dim in dim_fields_raw.split(",") if dim.strip()]
    grain = os.getenv("SAC_TIME_GRAIN", "month")

    if provider_id:
        raw_df = fetch_timeseries(
            provider_id=provider_id,
            namespace_id=namespace_id,
            config=config,
            slice_spec=DEFAULT_SLICE,
        )
        try:
            normalized_df = normalize_timeseries(raw_df)
        except NormalizeError as exc:
            raise ExportError(str(exc)) from exc
        normalized = normalized_df.to_dict(orient="records")
    else:
        if not export_url:
            raise ConfigError(
                "Missing SAC_PROVIDER_ID (preferred) or SAC_EXPORT_URL. "
                "See docs/dataset_binding.md."
            )
        rows = export_all(config, export_url, params=params)
        normalized = normalize_rows(
            rows,
            date_field=date_field,
            value_field=value_field,
            dim_fields=dim_fields,
            grain=grain,
        )
    if not normalized:
        raise ExportError("No rows returned from SAC export. See docs/dataset_binding.md.")
    columns = list(normalized[0].keys()) if normalized else []
    normalized_sorted = sorted(
        normalized,
        key=lambda r: tuple(r.get(col, "") for col in columns),
    )
    meta = build_meta(normalized_sorted, source="sac")
    save_cache(normalized_sorted, meta, data_path=output_path)
    return output_path, meta


def _refresh_from_fixture(output_path: str) -> str:
    fixture_path = "tests/fixtures/sample_series.csv"
    if not os.path.exists(fixture_path):
        raise ExportError("Fixture missing: tests/fixtures/sample_series.csv")
    with open(fixture_path, "r", encoding="utf-8") as handle:
        lines = handle.read().strip().splitlines()
    if len(lines) < 2:
        raise ExportError("Fixture is empty. Check tests/fixtures/sample_series.csv.")

    header = lines[0].split(",")
    rows = []
    for line in lines[1:]:
        values = line.split(",")
        rows.append(dict(zip(header, values)))

    normalized = normalize_rows(
        rows,
        date_field="date",
        value_field="value",
        dim_fields=["dim_region"],
        grain="month",
    )
    if not normalized:
        raise ExportError("No rows returned from fixture dataset.")

    columns = list(normalized[0].keys()) if normalized else []
    normalized_sorted = sorted(
        normalized,
        key=lambda r: tuple(r.get(col, "") for col in columns),
    )
    meta = build_meta(normalized_sorted, source="fixture")
    save_cache(normalized_sorted, meta, data_path=output_path)
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh cached dataset from SAC.")
    parser.add_argument("--source", default="sac", choices=["sac", "fixture"])
    parser.add_argument("--output", default="data/cache/sac_export.csv")
    args = parser.parse_args()

    try:
        if args.source == "fixture":
            output = _refresh_from_fixture(args.output)
            _, meta = load_cache(data_path=args.output)
        else:
            output, meta = refresh_from_sac(args.output)
    except ExportError as exc:
        try:
            _, meta = load_cache(data_path=args.output)
        except CacheError as cache_exc:
            print(str(exc))
            print(str(cache_exc))
            return 1
        warning = (
            "WARNING: SAC refresh failed; using cached data from "
            f"{meta.last_refresh_time}."
        )
        print(warning)
        print(
            "CACHE_META "
            f"source={meta.source} row_count={meta.row_count} "
            f"min_date={meta.min_date} max_date={meta.max_date}"
        )
        return 0
    except (ConfigError, ValueError) as exc:
        print(str(exc))
        return 1

    print(f"OK wrote {output}")
    print(
        "CACHE_META "
        f"source={meta.source} row_count={meta.row_count} "
        f"min_date={meta.min_date} max_date={meta.max_date}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
