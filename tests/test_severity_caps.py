from config.validation_caps import caps_for_severity


def test_caps_for_severity_operational_defaults():
    caps = caps_for_severity("operational")
    assert caps["mom_cap_default"] == 0.5


def test_caps_for_severity_crisis():
    caps = caps_for_severity("crisis")
    assert caps["mom_cap_default"] == 0.7
    assert caps["baseline_dev_warn_low"] == 0.3
