import config


def test_weights_sum_to_one():
    assert abs(sum(config.WEIGHTS.values()) - 1.0) < 1e-9
    assert set(config.WEIGHTS) == {"runway_pressure", "passengers", "load_factor", "growth_yoy"}


def test_years_are_prior_then_latest():
    assert len(config.YEARS) == 2 and config.YEARS[0] == config.YEARS[1] - 1


def test_new_england_region():
    assert config.REGIONS["new_england"] == ["MA", "CT", "RI", "NH", "VT", "ME"]
    for states in config.REGIONS.values():
        assert all(len(s) == 2 and s.isupper() for s in states)


def test_service_classes_do_not_overlap():
    assert not (config.PASSENGER_CLASSES & config.CARGO_CLASSES)
