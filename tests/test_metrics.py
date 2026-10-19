import json
import math

import numpy as np
import pandas as pd
import pytest

import metrics


def test_runway_counts_ignore_short_and_closed(synthetic):
    _, _, runways, _ = synthetic
    counts = metrics.runway_counts(runways)
    assert counts["KAAA"] == 2 and counts["KBBB"] == 1 and counts["KCCC"] == 1


def test_airport_metrics_latest_year(synthetic):
    od, *_ = synthetic
    m = metrics.airport_metrics(od, 2025)
    a = m.loc["AAA"]
    assert a.passengers == 1_000_000 and a.seats == 1_200_000 and a.departures == 10_000
    assert a.load_factor == pytest.approx(0.8333, abs=1e-4)
    assert a.departures_all == 12_000
    assert a.avg_stage_mi == pytest.approx(1280)
    assert a.intl_share == pytest.approx(2000 / 12000)
    assert a.state == "MA"
    assert m.loc["BBB"].intl_share == 0


def test_build_table_growth_pressure_universe_and_score(synthetic):
    od, airports, runways, _ = synthetic
    t = metrics.build_table(od, airports, runways, latest=2025, prior=2024)
    assert t.loc["AAA", "growth_yoy"] == pytest.approx(1_000_000 / 950_000 - 1)
    assert t.loc["BBB", "growth_yoy"] == pytest.approx(0.2)
    assert t.loc["AAA", "runways"] == 2 and t.loc["BBB", "runways"] == 1
    assert t.loc["AAA", "runway_pressure"] == pytest.approx(12_000 / 365 / 2)
    assert t.in_universe.to_dict() == {"AAA": True, "BBB": True, "CCC": False}
    assert t.loc["AAA", "score"] == 80.0 and t.loc["BBB", "score"] == 70.0
    assert math.isnan(t.loc["CCC", "score"])
    assert t.loc["AAA", "rank"] == 1 and t.loc["BBB", "rank"] == 2
    assert t.loc["AAA", "icao"] == "KAAA" and t.loc["AAA", "name"] == "Alpha Intl"
    assert (t.score.dropna().between(0, 100)).all()


def test_missing_runway_data_renormalizes_weights(synthetic):
    od, airports, runways, _ = synthetic
    t = metrics.build_table(od, airports, runways[runways.airport_ident != "KBBB"], latest=2025, prior=2024)
    assert math.isnan(t.loc["BBB", "runways"]) and math.isnan(t.loc["BBB", "pct_runway_pressure"])
    # BBB: passengers 0.5, load_factor 1.0, growth 1.0 over weights 0.25+0.25+0.15
    assert t.loc["BBB", "score"] == pytest.approx(100 * (0.25 * 0.5 + 0.25 * 1 + 0.15 * 1) / 0.65, abs=0.1)
    assert t.loc["AAA", "score"] == 80.0


def test_breakdown_contributions_sum_to_score(synthetic):
    od, airports, runways, _ = synthetic
    t = metrics.build_table(od, airports, runways, 2025, 2024)
    b = metrics.breakdown(t.loc["AAA"])
    assert [x["component"] for x in b] == ["runway_pressure", "passengers", "load_factor", "growth_yoy"]
    assert sum(x["contribution"] for x in b) == pytest.approx(80.0)
    assert b[0]["percentile"] == 1.0 and b[0]["weight"] == 0.35


def test_long_haul_shares_by_service_class(synthetic):
    od, *_ = synthetic
    lh = metrics.long_haul(od, "AAA", 2025, 1500)
    assert lh["passenger_service"]["long_haul_share_pct"] == 40.0
    assert lh["all_cargo"]["long_haul_share_pct"] == 100.0
    assert lh["passenger_service"]["top_long_haul_destinations"][0] == {"dest": "YYY", "country": "US", "departures": 4000.0}
    assert metrics.long_haul(od, "BBB", 2025, 1500)["all_cargo"]["long_haul_share_pct"] is None


def test_unmet_demand_flags_and_levels(synthetic):
    od, airports, runways, notes = synthetic
    t = metrics.build_table(od, airports, runways, 2025, 2024)
    median_growth = t[t.in_universe].growth_yoy.median()
    low = metrics.unmet_demand(t.loc["AAA"], notes, [], median_growth)
    assert low["flags"] == {"full_flights": False, "runway_constrained": True, "growing": False,
                            "live_congestion": False, "structural_constraint": False}
    assert low["level"] == "low"
    high = metrics.unmet_demand(t.loc["BBB"], notes, [{"type": "Ground Delay Programs"}], median_growth)
    assert high["flags_true"] == 4 and high["level"] == "high"


def test_select_states():
    assert metrics.select_states("new_england", None) == ["MA", "CT", "RI", "NH", "VT", "ME"]
    assert metrics.select_states("", ["ma", "ct"]) == ["MA", "CT"]
    assert metrics.select_states("", None) == []
    with pytest.raises(ValueError):
        metrics.select_states("narnia", None)


def test_jsonable_converts_numpy_and_nan():
    out = metrics.jsonable({"a": np.int64(1), "b": np.float64("nan"), "c": [np.bool_(True), np.float32(1.5)],
                            "d": pd.Timestamp("2026-01-01")})
    assert out == {"a": 1, "b": None, "c": [True, 1.5], "d": "2026-01-01 00:00:00"}
    json.dumps(out)
