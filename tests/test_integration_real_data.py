import json
import pathlib

import pytest

import config
import live
import tools

pytestmark = pytest.mark.skipif(
    not (pathlib.Path(config.DATA_DIR) / "t100_od_annual.csv.gz").exists(), reason="run scripts/fetch_data.py first")


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.setattr(live, "faa_status", lambda: {"updated": "test", "entries": {}})
    monkeypatch.setattr(live, "opensky_departures", lambda icao: {"status": "not configured"})


def test_universe_size_is_plausible():
    t, _ = tools._table()
    assert 60 <= t.in_universe.sum() <= 200


def test_new_england_filter_returns_only_new_england_and_includes_bos():
    out = tools.rank_airports(region="new_england")
    states = {a["state"] for a in out["ranking"]}
    assert states <= set(config.REGIONS["new_england"])
    assert "BOS" in {a["code"] for a in out["ranking"]}
    assert all(0 <= a["score"] <= 100 for a in out["ranking"])


def test_sfo_load_factor_is_plausible():
    p = tools.airport_profile("SFO")
    assert 60 <= p["load_factor_pct"] <= 95
    assert p["curated_notes"] and p["unmet_demand"]["level"] in {"low", "moderate", "high"}


def test_anc_cargo_is_more_long_haul_than_passenger_service():
    out = tools.long_haul_share("ANC")
    assert out["all_cargo"]["long_haul_share_pct"] > out["passenger_service"]["long_haul_share_pct"]
    assert out["all_cargo"]["top_long_haul_destinations"]


def test_sna_has_one_commercial_runway_and_lax_has_four():
    out = tools.compare_airports(["LAX", "SNA"])
    by = {a["code"]: a for a in out["airports"]}
    assert by["SNA"]["runways"] == 1 and by["LAX"]["runways"] == 4
    assert by["SNA"]["curated_notes"]


def test_metro_codes_exist_and_primaries_are_in_universe():
    t, d = tools._table()
    assert d["metros"], "data/metros.md is missing or empty"
    for metro, codes in d["metros"].items():
        missing = [c for c in codes if c not in t.index]
        assert not missing, (metro, missing)
        assert t.loc[codes[0], "in_universe"], f"{metro}: primary airport {codes[0]} is below the universe threshold"
    la = tools.search_airports("Los Angeles")
    airports = la["metros"][0]["airports"]
    assert airports[0]["code"] == "LAX" and airports[0]["primary"] and len(airports) == 5 and "ask" in la["hint"]
    assert len(tools.search_airports("Chicago")["matches"]) == 2 and "ask" in tools.search_airports("Chicago")["hint"]


def test_every_tool_result_is_json():
    for r in (tools.rank_airports(top_n=50), tools.airport_profile("BOS"), tools.compare_airports(["LAX", "SNA"]),
              tools.long_haul_share("ANC"), tools.live_status("SFO"), tools.search_airports("Santa Ana")):
        json.dumps(r)
