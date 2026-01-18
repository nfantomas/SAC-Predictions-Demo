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


def test_metric_mapping_cost_defaults():
    # No env overrides; defaults should pick cost measure and forecast/general filters
    mapping = get_metric_mapping()
    assert mapping.measure == "Cost"
    assert mapping.output_mode == "cost"
    assert mapping.filters == {"Version": "public.Forecast", "DataSource": "General"}
    assert mapping.calculation == "direct_measure"


def test_metric_mapping_fte_mode(monkeypatch):
    monkeypatch.setenv("HR_SERIES_MODE", "fte")
    mapping = get_metric_mapping()
    assert mapping.metric_name == "fte"
    assert mapping.unit == "fte"
    assert mapping.currency == ""
    assert mapping.calculation == "raw_fte"


def test_metric_mapping_fte_mode_rejects_cost(monkeypatch):
    monkeypatch.setenv("HR_SERIES_MODE", "fte")
    monkeypatch.setenv("HR_COST_MEASURE", "Cost")
    with pytest.raises(MetricMappingError):
        get_metric_mapping()
