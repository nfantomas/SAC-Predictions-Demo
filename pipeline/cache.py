import csv
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple


class CacheError(Exception):
    pass


@dataclass(frozen=True)
class CacheMeta:
    last_refresh_time: str
    source: str
    row_count: int
    min_date: str
    max_date: str


def _read_csv(path: str) -> List[Dict[str, str]]:
    if not os.path.exists(path):
        raise CacheError("Cache is missing or corrupt. Delete data/cache and rerun refresh.")
    with open(path, "r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = [dict(row) for row in reader]
    if not rows:
        raise CacheError("Cache is missing or corrupt. Delete data/cache and rerun refresh.")
    return rows


def _write_csv(path: str, rows: List[Dict]) -> None:
    if not rows:
        raise CacheError("Cache save failed: no rows to write.")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    columns = list(rows[0].keys())
    for row in rows:
        if list(row.keys()) != columns:
            raise CacheError("Cache save failed: rows must share the same schema.")
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def save_cache(
    rows: List[Dict],
    meta: CacheMeta,
    data_path: str = "data/cache/data.csv",
    meta_path: str = "data/cache/meta.json",
    extra_meta: Optional[Dict] = None,
) -> None:
    _write_csv(data_path, rows)
    os.makedirs(os.path.dirname(meta_path), exist_ok=True)
    payload = meta.__dict__.copy()
    if extra_meta:
        payload.update(extra_meta)
    with open(meta_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)


def load_cache(
    data_path: str = "data/cache/data.csv",
    meta_path: str = "data/cache/meta.json",
) -> Tuple[List[Dict[str, str]], CacheMeta]:
    rows = _read_csv(data_path)
    if not os.path.exists(meta_path):
        raise CacheError("Cache is missing or corrupt. Delete data/cache and rerun refresh.")
    try:
        with open(meta_path, "r", encoding="utf-8") as handle:
            meta_raw = json.load(handle)
    except json.JSONDecodeError as exc:
        raise CacheError("Cache is missing or corrupt. Delete data/cache and rerun refresh.") from exc

    required = {"last_refresh_time", "source", "row_count", "min_date", "max_date"}
    if not required.issubset(meta_raw):
        raise CacheError("Cache is missing or corrupt. Delete data/cache and rerun refresh.")

    return rows, CacheMeta(
        last_refresh_time=str(meta_raw["last_refresh_time"]),
        source=str(meta_raw["source"]),
        row_count=int(meta_raw["row_count"]),
        min_date=str(meta_raw["min_date"]),
        max_date=str(meta_raw["max_date"]),
    )


def load_cache_meta_raw(meta_path: str = "data/cache/meta.json") -> Dict[str, object]:
    if not os.path.exists(meta_path):
        raise CacheError("Cache is missing or corrupt. Delete data/cache and rerun refresh.")
    try:
        with open(meta_path, "r", encoding="utf-8") as handle:
            meta_raw = json.load(handle)
    except json.JSONDecodeError as exc:
        raise CacheError("Cache is missing or corrupt. Delete data/cache and rerun refresh.") from exc
    return meta_raw


def build_meta(rows: List[Dict], source: str) -> CacheMeta:
    dates = [row.get("date", "") for row in rows if row.get("date")]
    if not dates:
        raise CacheError("Cache metadata failed: missing date values.")
    return CacheMeta(
        last_refresh_time=datetime.now(timezone.utc).isoformat(),
        source=source,
        row_count=len(rows),
        min_date=min(dates),
        max_date=max(dates),
    )
