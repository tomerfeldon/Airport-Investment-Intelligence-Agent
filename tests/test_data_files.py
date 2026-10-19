import pathlib

import pandas as pd
import pytest

import config

DATA = pathlib.Path(config.DATA_DIR)
pytestmark = pytest.mark.skipif(
    not (DATA / "t100_od_annual.csv.gz").exists(), reason="run scripts/fetch_data.py first"
)

SCHEMA = ["year", "origin", "origin_state", "dest", "dest_country", "svc_class",
          "departures", "seats", "passengers", "freight", "distance"]


def test_t100_schema_years_and_filters():
    od = pd.read_csv(DATA / "t100_od_annual.csv.gz")
    assert list(od.columns) == SCHEMA
    assert sorted(od.year.unique().tolist()) == config.YEARS
    assert (od.departures > 0).all()
    assert set(od.svc_class.unique()) <= {"F", "L", "G", "P"}
    assert {"SFO", "BOS", "ANC", "SNA", "LAX"} <= set(od.origin)
    assert (DATA / "t100_od_annual.csv.gz").stat().st_size < 5_000_000


def test_airports_and_runways_files():
    ap = pd.read_csv(DATA / "airports_us.csv")
    rw = pd.read_csv(DATA / "runways_us.csv")
    assert {"SFO", "BOS", "ANC", "SNA", "LAX"} <= set(ap.iata_code)
    assert rw.airport_ident.isin(ap.ident).all()
    assert {"length_ft", "closed"} <= set(rw.columns)


def test_airport_notes_schema():
    import agentfiles
    notes = agentfiles.notes(DATA / "airport_notes.md")
    assert {"SNA", "SFO", "DCA", "ANC"} <= set(notes)
    for code, items in notes.items():
        assert code.isupper() and len(code) == 3 and items
        for n in items:
            assert n["type"] in {"constraint", "context"}
            assert n["text"] and n["source"].startswith("https://") and n["verified"]
