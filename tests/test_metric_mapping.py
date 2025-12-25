import pytest

from pipeline.metric_mapping import MetricMappingError, get_metric_mapping


def test_metric_mapping_rejects_bad_measure(monkeypatch):
    monkeypatch.setenv("HR_COST_MEASURE", "BadMeasure")
    with pytest.raises(MetricMappingError):
        get_metric_mapping()


def test_metric_mapping_filters_override(monkeypatch):
    monkeypatch.setenv("HR_COST_FILTERS_JSON", '{"Version": "public.Actual"}')
    mapping = get_metric_mapping()
    assert mapping.filters["Version"] == "public.Actual"
