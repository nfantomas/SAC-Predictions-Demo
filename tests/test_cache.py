import pytest

from pipeline.cache import CacheError, build_meta, load_cache, save_cache


def test_save_then_load(tmp_path):
    rows = [
        {"date": "2024-01-01", "value": "1.0", "dim_region": "NA"},
        {"date": "2024-02-01", "value": "2.0", "dim_region": "NA"},
    ]
    meta = build_meta(rows, source="fixture")
    data_path = tmp_path / "data.csv"
    meta_path = tmp_path / "meta.json"

    save_cache(rows, meta, data_path=str(data_path), meta_path=str(meta_path))
    loaded_rows, loaded_meta = load_cache(
        data_path=str(data_path), meta_path=str(meta_path)
    )

    assert loaded_rows == rows
    assert loaded_meta.source == "fixture"
    assert loaded_meta.row_count == 2


def test_corrupt_cache_raises(tmp_path):
    data_path = tmp_path / "data.csv"
    meta_path = tmp_path / "meta.json"
    data_path.write_text("date,value\n", encoding="utf-8")
    meta_path.write_text("not-json", encoding="utf-8")

    with pytest.raises(CacheError) as exc:
        load_cache(data_path=str(data_path), meta_path=str(meta_path))

    assert "Delete data/cache" in str(exc.value)
