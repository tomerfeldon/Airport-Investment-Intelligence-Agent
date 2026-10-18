import json

import pytest

import live
import metrics
import tools


@pytest.fixture
def fake_table(synthetic, monkeypatch):
    od, airports, runways, notes = synthetic
    t = metrics.build_table(od, airports, runways, 2025, 2024)
    monkeypatch.setattr(tools, "_table", lambda: (t, {"od": od, "airports": airports, "runways": runways, "notes": notes}))
    monkeypatch.setattr(live, "faa_status", lambda: {"updated": "now", "entries": {"BBB": [{"type": "Ground Delay Programs", "Reason": "WX"}]}})
    monkeypatch.setattr(live, "opensky_departures", lambda icao: {"status": "not configured"})
    return t


def test_rank_all_and_region(fake_table):
    out = tools.rank_airports()
    assert [a["code"] for a in out["ranking"]] == ["AAA", "BBB"]
    assert [a["score"] for a in out["ranking"]] == [80.0, 70.0]
    assert out["ranking"][0]["breakdown"][0]["component"] == "runway_pressure"
    assert out["meta"]["universe_size"] == 2 and out["methodology"]["weights"]["runway_pressure"] == 0.35
    json.dumps(out)
    ne = tools.rank_airports(region="new_england")
    assert [a["code"] for a in ne["ranking"]] == ["AAA"] and ne["filter"]["states"][0] == "MA"
    assert [a["code"] for a in tools.rank_airports(states=["ca"])["ranking"]] == ["BBB"]
    assert "error" in tools.rank_airports(region="narnia")


def test_profile_unmet_live_and_notes(fake_table):
    p = tools.airport_profile("bbb")
    assert p["code"] == "BBB" and p["load_factor_pct"] == 92.3 and p["runways"] == 1
    assert p["unmet_demand"]["level"] == "high"
    assert p["live"]["faa"]["entries"][0]["Reason"] == "WX" and p["live"]["opensky"]["status"] == "not configured"
    assert p["curated_notes"][0]["type"] == "constraint"
    json.dumps(p)
    assert "error" in tools.airport_profile("ZZZ") and "search_airports" in tools.airport_profile("ZZZ")["hint"]


def test_below_universe_profile_has_no_score_but_a_caveat(fake_table):
    p = tools.airport_profile("CCC")
    assert p["score"] is None and any("Below the universe threshold" in c for c in p["caveats"])


def test_compare_bounds_and_content(fake_table):
    out = tools.compare_airports(["AAA", "bbb"])
    assert [a["code"] for a in out["airports"]] == ["AAA", "BBB"]
    json.dumps(out)
    assert "error" in tools.compare_airports(["AAA"])
    assert "error" in tools.compare_airports(["AAA", "ZZZ"])


def test_long_haul_tool(fake_table):
    out = tools.long_haul_share("AAA")
    assert out["passenger_service"]["long_haul_share_pct"] == 40.0 and out["threshold_miles"] == 1500
    assert out["curated_notes"] == [] and "meta" in out
    json.dumps(out)
    assert tools.long_haul_share("AAA", threshold_miles=2500)["passenger_service"]["long_haul_share_pct"] == 0.0


def test_search_and_live_status(fake_table):
    assert [m["code"] for m in tools.search_airports("bravo")["matches"]] == ["BBB"]
    assert [m["code"] for m in tools.search_airports("AAA")["matches"]] == ["AAA"]
    assert tools.search_airports("nowhere")["matches"] == []
    ls = tools.live_status("AAA")
    assert ls["faa"]["entries"] == [] and ls["opensky"]["status"] == "not configured"
    json.dumps(ls)
