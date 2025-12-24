from demo.refresh import _refresh_from_fixture
from pipeline.cache import load_cache


def test_refresh_from_fixture(tmp_path):
    output = tmp_path / "fixture.csv"
    _refresh_from_fixture(str(output))
    rows, meta = load_cache(data_path=str(output))
    assert rows
    assert meta.source == "fixture"
