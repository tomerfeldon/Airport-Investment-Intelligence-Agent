# Airport Investment Intelligence Agent — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Streamlit chat agent that ranks and explains US airports as capacity-expansion investment opportunities, with every number produced by deterministic Python over public data and Gemini used only to route questions to tools and narrate results.

**Architecture:** `app.py` (Streamlit chat) → `agent.py` (Gemini manual tool-calling loop, ≤ 6 iterations, returns answer + tool trace) → `tools.py` (six deterministic functions returning JSON) → `metrics.py` (pandas: per-airport table, Expansion Opportunity Score, breakdown, long-haul, unmet-demand) + `live.py` (FAA XML, optional OpenSky) + `config.py` (all knobs). `scripts/fetch_data.py` builds the committed `data/` files offline from BTS TranStats and OurAirports.

**Tech Stack:** Python 3.12, pandas, requests, streamlit, google-genai (2.31+), python-dotenv, pytest. Model `gemini-3.8-flash` (free tier, stable).

**Spec:** `docs/superpowers/specs/2026-10-18-airport-agent-design.md`. Deviations from the spec, decided while verifying: (1) tool results expose ready-made percentage fields (`*_pct`) so the model never does arithmetic; (2) the OpenSky overlay reports yesterday's departure count and top destinations only — the live long-haul share needs world-wide airport coordinates and was cut (YAGNI); (3) airport state comes from T-100 `ORIGIN_STATE_ABR`, not OurAirports `iso_region`.

## Global Constraints

- Python 3.12 on the dev machine (Windows, Git Bash). Commands below use `.venv/Scripts/python.exe`; on macOS/Linux use `.venv/bin/python`.
- Dependencies are exactly: `streamlit>=1.40`, `pandas>=2.2`, `requests>=2.32`, `google-genai>=1.30`, `python-dotenv>=1.0`, `pytest>=8`. No others.
- Every number shown to the user comes from `metrics.py`/`live.py`; the LLM never computes a metric.
- All tunables live in `config.py`: `YEARS = [2024, 2025]` (prior, latest), `UNIVERSE_MIN_PASSENGERS = 500_000`, `MIN_RUNWAY_FT = 5000`, `LONG_HAUL_MILES = 1500`, `PASSENGER_CLASSES = {"F", "L"}`, `CARGO_CLASSES = {"G", "P"}`, `WEIGHTS` summing to 1.0 (`runway_pressure 0.35, passengers 0.25, load_factor 0.25, growth_yoy 0.15`), `UNMET = {"load_factor": 0.85, "pressure_pct": 0.80}`, `MODEL = "gemini-3.8-flash"` (overridable by `GEMINI_MODEL`).
- Live signals (FAA, OpenSky) are never part of the score.
- Tool results must be JSON-serializable (`json.dumps` must succeed) and must never raise; errors are returned as `{"error": "..."}`.
- Processed data files are committed; raw zips (`data/raw/`) and `.env` are gitignored (already in `.gitignore`).
- Modules live flat at the repo root (`app.py`, `agent.py`, `tools.py`, `metrics.py`, `live.py`, `config.py`); tests in `tests/`; scripts in `scripts/`.
- Processed T-100 schema (lower-case): `year, origin, origin_state, dest, dest_country, svc_class, departures, seats, passengers, freight, distance`.
- Commit after every task; commit messages without attribution lines.

## File structure

| File | Responsibility |
|---|---|
| `config.py` | Every tunable constant; nothing else |
| `scripts/fetch_data.py` | Offline: replay TranStats form for table FMG per year → aggregate → `data/t100_od_annual.csv.gz`; OurAirports → `data/airports_us.csv`, `data/runways_us.csv` |
| `data/airport_notes.json` | Four hand-verified structural facts with sources |
| `metrics.py` | Pure pandas: `load`, `airport_metrics`, `runway_counts`, `build_table`, `score`, `breakdown`, `long_haul`, `unmet_demand`, `select_states`, `jsonable` |
| `live.py` | `parse_faa`, `faa_status` (60 s cache), `opensky_configured`, `opensky_departures` |
| `tools.py` | Six tools the model may call; `_table`, `_meta`, `_methodology`, `_row_summary` helpers |
| `agent.py` | `SYSTEM_PROMPT`, `ask(history, text)`, `transcribe(audio, mime)`, CLI entry point |
| `app.py` | Streamlit chat, sidebar methodology, example buttons, trace expander, optional voice |
| `tests/conftest.py` | Synthetic three-airport fixture shared by unit tests |
| `tests/test_config.py`, `tests/test_metrics.py`, `tests/test_live.py`, `tests/test_tools.py`, `tests/test_data_files.py`, `tests/test_integration_real_data.py` | Tests per module; the last two skip when `data/` is absent |
| `DESIGN.md`, `README.md` | Deliverable documents |

---

### Task 1: Project skeleton and config

**Files:**
- Create: `requirements.txt`, `pyproject.toml`, `.env.example`, `config.py`, `tests/__init__.py` (empty), `tests/test_config.py`

**Interfaces:**
- Produces: `config.MODEL: str`, `config.YEARS: list[int]`, `config.DATA_DIR: str`, `config.UNIVERSE_MIN_PASSENGERS: int`, `config.MIN_RUNWAY_FT: int`, `config.LONG_HAUL_MILES: int`, `config.PASSENGER_CLASSES: set[str]`, `config.CARGO_CLASSES: set[str]`, `config.WEIGHTS: dict[str, float]`, `config.UNMET: dict[str, float]`, `config.REGIONS: dict[str, list[str]]`

- [ ] **Step 1: Create the environment files**

`requirements.txt`:
```
streamlit>=1.40
pandas>=2.2
requests>=2.32
google-genai>=1.30
python-dotenv>=1.0
pytest>=8
```

`pyproject.toml`:
```toml
[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

`.env.example`:
```
# Required. Free key: https://aistudio.google.com/apikey
GEMINI_API_KEY=
# Optional
GEMINI_MODEL=gemini-3.8-flash
# Optional live overlay. Free account: https://opensky-network.org -> Account -> API client
OPENSKY_CLIENT_ID=
OPENSKY_CLIENT_SECRET=
```

- [ ] **Step 2: Create the venv and install**

Run:
```bash
cd "/c/Project/home task - wonderful" && python -m venv .venv && .venv/Scripts/python.exe -m pip install -q -r requirements.txt && .venv/Scripts/python.exe -c "import streamlit, pandas, requests, google.genai, dotenv, pytest; print('ok')"
```
Expected: `ok`

- [ ] **Step 3: Write the failing config test**

`tests/__init__.py`: empty file.

`tests/test_config.py`:
```python
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
```

- [ ] **Step 4: Run it to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_config.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'config'`

- [ ] **Step 5: Write config.py**

```python
"""Every tunable knob of the agent. DESIGN.md explains each choice; nothing else lives here."""
import os

MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")

DATA_DIR = "data"
YEARS = [2024, 2025]                      # [prior, latest]; both must be complete calendar years in T-100

UNIVERSE_MIN_PASSENGERS = 500_000         # originating passengers (passenger service) in the latest year
MIN_RUNWAY_FT = 5000                      # shorter runways do not add commercial capacity
LONG_HAUL_MILES = 1500                    # default threshold for "long haul" segments

PASSENGER_CLASSES = {"F", "L"}            # T-100 CLASS: scheduled (F) and non-scheduled (L) passenger service
CARGO_CLASSES = {"G", "P"}                # scheduled (G) and non-scheduled (P) all-cargo service

# Expansion Opportunity Score = 100 * sum(weight * percentile rank within the universe). Must sum to 1.0.
WEIGHTS = {
    "runway_pressure": 0.35,              # departures per runway per day — the physical bottleneck
    "passengers": 0.25,                   # market size
    "load_factor": 0.25,                  # full aircraft = demand airlines cannot add seats for
    "growth_yoy": 0.15,                   # direction of travel
}

# Unmet-demand flag thresholds
UNMET = {"load_factor": 0.85, "pressure_pct": 0.80}

REGIONS = {
    "new_england": ["MA", "CT", "RI", "NH", "VT", "ME"],
    "mid_atlantic": ["NY", "NJ", "PA", "DE", "MD", "DC", "VA", "WV"],
    "southeast": ["NC", "SC", "GA", "FL", "AL", "MS", "TN", "KY"],
    "midwest": ["OH", "MI", "IN", "IL", "WI", "MN", "IA", "MO", "ND", "SD", "NE", "KS"],
    "texas": ["TX", "OK", "LA", "AR"],
    "mountain_west": ["CO", "UT", "NV", "AZ", "NM", "ID", "MT", "WY"],
    "west_coast": ["CA"],
    "pacific_northwest": ["WA", "OR"],
    "alaska_hawaii": ["AK", "HI"],
}
```

- [ ] **Step 6: Run the tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_config.py -q`
Expected: `4 passed`

- [ ] **Step 7: Commit**

```bash
git add requirements.txt pyproject.toml .env.example config.py tests/__init__.py tests/test_config.py
git commit -m "Add project skeleton and config"
```

---

### Task 2: Data pipeline — `scripts/fetch_data.py` and committed data

**Files:**
- Create: `scripts/fetch_data.py`, `tests/test_data_files.py`
- Produces (committed): `data/t100_od_annual.csv.gz`, `data/airports_us.csv`, `data/runways_us.csv`

**Interfaces:**
- Consumes: `config.YEARS`, `config.DATA_DIR`
- Produces: `data/t100_od_annual.csv.gz` with columns `year, origin, origin_state, dest, dest_country, svc_class, departures, seats, passengers, freight, distance`; `data/airports_us.csv` with `ident, icao_code, iata_code, name, municipality, iso_region, latitude_deg, longitude_deg, type`; `data/runways_us.csv` with `airport_ident, length_ft, width_ft, surface, closed, le_ident, he_ident`

Background for the implementer: BTS TranStats has no download URL — the "Download" button posts an ASP.NET WebForms form. The POST works from a script only when (a) the session cookie from the GET is sent back and (b) the hidden `__VIEWSTATE`, `__VIEWSTATEGENERATOR`, `__EVENTVALIDATION` values are echoed. Table code `FMG` = "T-100 Segment (All Carriers)" = domestic + international, US + foreign carriers. Verified 2026-10-18: 2025 is complete (12 months, 571,205 rows, ~7 MB zip).

- [ ] **Step 1: Write the failing data-file test**

`tests/test_data_files.py`:
```python
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
```

- [ ] **Step 2: Run it — it must skip (no data yet)**

Run: `.venv/Scripts/python.exe -m pytest tests/test_data_files.py -q`
Expected: `2 skipped`

- [ ] **Step 3: Write the fetch script**

`scripts/fetch_data.py`:
```python
"""Build data/ from public sources. Run once: python scripts/fetch_data.py

BTS TranStats has no stable download URL, so we replay its download form (table FMG =
T-100 Segment, All Carriers). The POST only works with the session cookie and the ASP.NET
hidden fields from the GET. Raw zips are cached in data/raw/ (gitignored); the committed
output is the small annual origin-destination-class aggregate the app actually needs.
"""
import html
import pathlib
import re
import sys
import zipfile

import pandas as pd
import requests

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import config  # noqa: E402

TRANSTATS = "https://www.transtats.bts.gov/DL_SelectFields.aspx?gnoyr_VQ=FMG&QO_fu146_anzr=Nv4%20Pn44vr45"
FIELDS = ["DEPARTURES_PERFORMED", "SEATS", "PASSENGERS", "FREIGHT", "DISTANCE", "ORIGIN", "ORIGIN_STATE_ABR",
          "ORIGIN_COUNTRY", "DEST", "DEST_STATE_ABR", "DEST_COUNTRY", "YEAR", "MONTH", "CLASS"]
OURAIRPORTS = "https://davidmegginson.github.io/ourairports-data/"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/130.0 Safari/537.36"}
DATA = pathlib.Path(config.DATA_DIR)
RAW = DATA / "raw"
SCHEMA = {"YEAR": "year", "ORIGIN": "origin", "ORIGIN_STATE_ABR": "origin_state", "DEST": "dest",
          "DEST_COUNTRY": "dest_country", "CLASS": "svc_class"}


def fetch_t100_year(year: int) -> pd.DataFrame:
    cached = RAW / f"t100_{year}.zip"
    if not cached.exists():
        s = requests.Session()
        s.headers.update(UA)
        page = s.get(TRANSTATS, timeout=90).text
        form = {k: html.unescape(re.search(rf'<input[^>]*name="{k}"[^>]*value="([^"]*)"', page).group(1))
                for k in ("__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION")}
        form.update({"__EVENTTARGET": "", "__EVENTARGUMENT": "", "__LASTFOCUS": "", "cboGeography": "All",
                     "cboYear": str(year), "cboPeriod": "All", "btnDownload": "Download"})
        form.update({f: "on" for f in FIELDS})
        r = s.post(TRANSTATS, data=form, headers={"Referer": TRANSTATS}, timeout=900)
        if r.content[:2] != b"PK":
            raise RuntimeError(f"TranStats returned no zip for {year}. Download it manually from {TRANSTATS} "
                               f"(fields: {', '.join(FIELDS)}) and save it as {cached}")
        cached.write_bytes(r.content)
        print(f"downloaded {cached} ({len(r.content) / 1e6:.1f} MB)")
    with zipfile.ZipFile(cached) as z:
        return pd.read_csv(z.open(z.namelist()[0]))


def aggregate(raw: pd.DataFrame) -> pd.DataFrame:
    """Annual origin x destination x class totals for US-origin segments that actually flew."""
    raw = raw[(raw.DEPARTURES_PERFORMED > 0) & (raw.ORIGIN_COUNTRY == "US")]
    agg = (raw.groupby(list(SCHEMA), as_index=False, dropna=False)
              .agg(departures=("DEPARTURES_PERFORMED", "sum"), seats=("SEATS", "sum"),
                   passengers=("PASSENGERS", "sum"), freight=("FREIGHT", "sum"), distance=("DISTANCE", "median"))
              .rename(columns=SCHEMA))
    return agg


def fetch_ourairports() -> None:
    ap = pd.read_csv(OURAIRPORTS + "airports.csv")
    ap = ap[(ap.iso_country == "US") & ap.iata_code.notna()
            & ap.type.isin(["large_airport", "medium_airport", "small_airport"])]
    ap = ap[["ident", "icao_code", "iata_code", "name", "municipality", "iso_region",
             "latitude_deg", "longitude_deg", "type"]]
    rw = pd.read_csv(OURAIRPORTS + "runways.csv")
    rw = rw[rw.airport_ident.isin(ap.ident)][["airport_ident", "length_ft", "width_ft", "surface",
                                                "closed", "le_ident", "he_ident"]]
    ap.to_csv(DATA / "airports_us.csv", index=False)
    rw.to_csv(DATA / "runways_us.csv", index=False)
    print(f"airports: {len(ap)} rows, runways: {len(rw)} rows")


if __name__ == "__main__":
    DATA.mkdir(exist_ok=True)
    RAW.mkdir(exist_ok=True)
    od = pd.concat([aggregate(fetch_t100_year(y)) for y in config.YEARS], ignore_index=True)
    od.to_csv(DATA / "t100_od_annual.csv.gz", index=False, compression="gzip")
    print(f"t100: {len(od)} rows for years {config.YEARS}")
    fetch_ourairports()
    print("done")
```

- [ ] **Step 4: Run the script (2–5 minutes; TranStats is slow)**

Run: `.venv/Scripts/python.exe scripts/fetch_data.py`
Expected (numbers approximate):
```
downloaded data/raw/t100_2024.zip (7.x MB)
downloaded data/raw/t100_2025.zip (7.2 MB)
t100: ~90000 rows for years [2024, 2025]
airports: ~1500 rows, runways: ~3000 rows
done
```
If TranStats returns HTML instead of a zip, the script prints manual instructions; follow them (browser download, same field list, save as `data/raw/t100_<year>.zip`) and rerun.

- [ ] **Step 5: Run the data tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_data_files.py -q`
Expected: `2 passed`

- [ ] **Step 6: Check sizes and commit**

Run: `ls -la data/ && git status --short`
Expected: `t100_od_annual.csv.gz` under 5 MB; `data/raw/` not listed (gitignored).

```bash
git add scripts/fetch_data.py tests/test_data_files.py data/t100_od_annual.csv.gz data/airports_us.csv data/runways_us.csv
git commit -m "Add data pipeline and committed BTS T-100 / OurAirports extracts"
```

---

### Task 3: `metrics.py` core — per-airport table and score

**Files:**
- Create: `metrics.py`, `tests/conftest.py`, `tests/test_metrics.py`

**Interfaces:**
- Consumes: `config.*`; data frames with the schemas from Task 2
- Produces:
  - `metrics.runway_counts(runways: pd.DataFrame) -> pd.Series` (index `airport_ident`)
  - `metrics.airport_metrics(od: pd.DataFrame, year: int) -> pd.DataFrame` (index IATA; columns `passengers, seats, departures, avg_stage_mi, load_factor, departures_all, intl_share, state`)
  - `metrics.build_table(od, airports, runways, latest: int, prior: int) -> pd.DataFrame` (index IATA; adds `growth_yoy, name, municipality, ident, icao, latitude_deg, longitude_deg, runways, runway_pressure, in_universe, score, pct_<component>, rank`)
  - `metrics.score(t: pd.DataFrame) -> pd.DataFrame`
  - `metrics.load() -> dict` with keys `od, airports, runways, notes` (notes file arrives in Task 6; `load` tolerates its absence by returning `{}`)

Synthetic fixture arithmetic (used by the asserts): AAA passengers 1,000,000 / seats 1,200,000 → LF 0.8333; passenger departures 10,000; all-class departures 12,000; 2 counted runways → pressure 12,000/365/2 = 16.438; growth 1,000,000/950,000 − 1 = 0.05263; avg stage (6,000·800 + 4,000·2,000)/10,000 = 1,280 mi; intl share 2,000/12,000 = 0.1667. BBB: LF 0.9231, 1 runway → pressure 13.699, growth 0.20. CCC: 100,000 passengers → below universe. Universe = {AAA, BBB}, so percentiles are 0.5/1.0 → AAA score 80.0, BBB 70.0.

- [ ] **Step 1: Write the shared fixture**

`tests/conftest.py`:
```python
import pandas as pd
import pytest

OD_COLUMNS = ["year", "origin", "origin_state", "dest", "dest_country", "svc_class",
              "departures", "seats", "passengers", "freight", "distance"]


@pytest.fixture
def synthetic():
    """Three airports: AAA big with 2 usable runways, BBB busy single runway, CCC below the universe."""
    od = pd.DataFrame([
        (2025, "AAA", "MA", "XXX", "US", "F", 6000, 720000, 600000, 0, 800),
        (2025, "AAA", "MA", "YYY", "US", "F", 4000, 480000, 400000, 0, 2000),
        (2025, "AAA", "MA", "ZZZ", "JP", "G", 2000, 0, 0, 50000, 3000),
        (2025, "BBB", "CA", "XXX", "US", "F", 5000, 650000, 600000, 0, 400),
        (2025, "CCC", "VT", "XXX", "US", "F", 1000, 150000, 100000, 0, 500),
        (2024, "AAA", "MA", "XXX", "US", "F", 9500, 1150000, 950000, 0, 800),
        (2024, "BBB", "CA", "XXX", "US", "F", 5000, 650000, 500000, 0, 400),
        (2024, "CCC", "VT", "XXX", "US", "F", 1000, 150000, 100000, 0, 500),
    ], columns=OD_COLUMNS)
    airports = pd.DataFrame([
        ("KAAA", "KAAA", "AAA", "Alpha Intl", "Alphaville", "US-MA", 42.0, -71.0, "large_airport"),
        ("KBBB", "KBBB", "BBB", "Bravo Field", "Bravotown", "US-CA", 33.0, -117.0, "medium_airport"),
        ("KCCC", "KCCC", "CCC", "Charlie Regional", "Charlieburg", "US-VT", 44.0, -73.0, "small_airport"),
    ], columns=["ident", "icao_code", "iata_code", "name", "municipality", "iso_region",
                "latitude_deg", "longitude_deg", "type"])
    runways = pd.DataFrame([
        ("KAAA", 10000, 150, "ASP", 0, "04", "22"),
        ("KAAA", 8000, 150, "ASP", 0, "09", "27"),
        ("KAAA", 3000, 75, "ASP", 0, "15", "33"),    # too short: must not count
        ("KAAA", 9000, 150, "ASP", 1, "01", "19"),    # closed: must not count
        ("KBBB", 5701, 150, "ASP", 0, "20R", "02L"),
        ("KCCC", 7000, 150, "ASP", 0, "15", "33"),
    ], columns=["airport_ident", "length_ft", "width_ft", "surface", "closed", "le_ident", "he_ident"])
    notes = {"BBB": [{"type": "constraint", "text": "Single runway and a legal passenger cap.",
                      "source": "https://example.com/settlement"}]}
    return od, airports, runways, notes
```

- [ ] **Step 2: Write the failing metrics tests**

`tests/test_metrics.py`:
```python
import math

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
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_metrics.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'metrics'`

- [ ] **Step 4: Write metrics.py (core)**

`metrics.py`:
```python
"""Deterministic metrics and the Expansion Opportunity Score. No LLM anywhere in this file.

All functions take DataFrames so tests can inject synthetic data; load() reads the committed files.
"""
from __future__ import annotations

import functools
import json
import pathlib

import numpy as np
import pandas as pd

import config

DATA = pathlib.Path(config.DATA_DIR)


@functools.lru_cache(maxsize=1)
def load() -> dict:
    """Read the committed data files once."""
    notes_path = DATA / "airport_notes.json"
    return {
        "od": pd.read_csv(DATA / "t100_od_annual.csv.gz"),
        "airports": pd.read_csv(DATA / "airports_us.csv"),
        "runways": pd.read_csv(DATA / "runways_us.csv"),
        "notes": json.loads(notes_path.read_text(encoding="utf-8")) if notes_path.exists() else {},
    }


def runway_counts(runways: pd.DataFrame) -> pd.Series:
    """Open runways of at least MIN_RUNWAY_FT per OurAirports ident."""
    ok = runways[(runways.closed == 0) & (runways.length_ft >= config.MIN_RUNWAY_FT)]
    return ok.groupby("airport_ident").size()


def airport_metrics(od: pd.DataFrame, year: int) -> pd.DataFrame:
    """Per-origin metrics for one year. Index = airport code (T-100 ORIGIN, IATA for the universe)."""
    y = od[od.year == year]
    pax = y[y.svc_class.isin(config.PASSENGER_CLASSES)]
    g = pax.groupby("origin")
    out = pd.DataFrame({"passengers": g.passengers.sum(), "seats": g.seats.sum(), "departures": g.departures.sum()})
    out["avg_stage_mi"] = (pax.distance * pax.departures).groupby(pax.origin).sum() / out.departures
    out["load_factor"] = out.passengers / out.seats
    ga = y.groupby("origin")
    out["departures_all"] = ga.departures.sum()                     # all classes: cargo uses runways too
    intl = y[y.dest_country != "US"].groupby("origin").departures.sum()
    out["intl_share"] = intl.reindex(out.index).fillna(0) / out.departures_all
    out["state"] = ga.origin_state.first()
    return out


def build_table(od: pd.DataFrame, airports: pd.DataFrame, runways: pd.DataFrame, latest: int, prior: int) -> pd.DataFrame:
    """The one table everything else reads from: metrics + airport facts + runways + score."""
    cur = airport_metrics(od, latest)
    prev = airport_metrics(od, prior)
    cur["growth_yoy"] = cur.passengers / prev.passengers.reindex(cur.index) - 1
    # "large_airport" < "medium_airport" < "small_airport" alphabetically, so the biggest wins a duplicate IATA code
    ap = airports.sort_values("type").drop_duplicates("iata_code").set_index("iata_code")
    cur = cur.join(ap[["name", "municipality", "ident", "icao_code", "latitude_deg", "longitude_deg"]])
    cur["icao"] = cur.icao_code.fillna(cur.ident)
    cur["runways"] = runway_counts(runways).reindex(cur.ident).values
    cur["runway_pressure"] = cur.departures_all / 365 / cur.runways
    cur["in_universe"] = cur.passengers >= config.UNIVERSE_MIN_PASSENGERS
    cur = cur.replace([np.inf, -np.inf], np.nan)
    return score(cur)


def score(t: pd.DataFrame) -> pd.DataFrame:
    """Percentile-rank each component within the universe, weight, sum to 0-100.

    A missing component (NaN) drops out and the remaining weights are renormalized, so an
    airport without runway data still gets a score - with a caveat added by tools.py.
    """
    t = t.copy()
    u = t[t.in_universe]
    pct = pd.DataFrame({c: u[c].rank(pct=True) for c in config.WEIGHTS})
    w = pd.Series(config.WEIGHTS)
    weight_present = pct.notna().mul(w, axis=1).sum(axis=1)
    t["score"] = (pct.mul(w, axis=1).sum(axis=1) / weight_present * 100).round(1)
    for c in config.WEIGHTS:
        t[f"pct_{c}"] = pct[c]
    t["rank"] = t.score.rank(ascending=False, method="min")
    return t
```

- [ ] **Step 5: Run the tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_metrics.py -q`
Expected: `4 passed`

- [ ] **Step 6: Commit**

```bash
git add metrics.py tests/conftest.py tests/test_metrics.py
git commit -m "Add per-airport metrics table and Expansion Opportunity Score"
```

---

### Task 4: `metrics.py` — breakdown, long-haul, unmet demand, helpers

**Files:**
- Modify: `metrics.py` (append)
- Modify: `tests/test_metrics.py` (append)

**Interfaces:**
- Produces:
  - `metrics.breakdown(row: pd.Series) -> list[dict]` with keys `component, raw, percentile, weight, contribution`
  - `metrics.long_haul(od, code: str, year: int, threshold: int) -> dict` with keys `airport, year, threshold_miles, passenger_service, all_cargo, definition`; each service dict has `departures, long_haul_departures, long_haul_share_pct, top_long_haul_destinations`
  - `metrics.unmet_demand(row, notes: dict, faa_entries: list, median_growth: float) -> dict` with keys `flags, flags_true, level, thresholds, note`
  - `metrics.select_states(region: str, states: list[str] | None) -> list[str]` (raises `ValueError` on unknown region)
  - `metrics.jsonable(x)` — recursive numpy/NaN → JSON-safe

- [ ] **Step 1: Append the failing tests**

Append to `tests/test_metrics.py`:
```python


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
    assert "not observable" in high["note"]


def test_select_states():
    assert metrics.select_states("new_england", None) == ["MA", "CT", "RI", "NH", "VT", "ME"]
    assert metrics.select_states("", ["ma", "ct"]) == ["MA", "CT"]
    assert metrics.select_states("", None) == []
    with pytest.raises(ValueError):
        metrics.select_states("narnia", None)


def test_jsonable_converts_numpy_and_nan():
    import json
    import numpy as np
    out = metrics.jsonable({"a": np.int64(1), "b": np.float64("nan"), "c": [np.bool_(True), np.float32(1.5)],
                            "d": pd.Timestamp("2026-01-01")})
    assert out == {"a": 1, "b": None, "c": [True, 1.5], "d": "2026-01-01 00:00:00"}
    json.dumps(out)
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_metrics.py -q`
Expected: `4 passed, 5 failed` with `AttributeError: module 'metrics' has no attribute 'breakdown'` etc.

- [ ] **Step 3: Append the implementation to metrics.py**

```python


def breakdown(row: pd.Series) -> list[dict]:
    """One line per score component: raw value, percentile, weight, contribution (points)."""
    out = []
    for c, w in config.WEIGHTS.items():
        p = row.get(f"pct_{c}")
        has = pd.notna(p)
        out.append({
            "component": c,
            "raw": row.get(c),
            "percentile": round(float(p), 3) if has else None,
            "weight": w,
            "contribution": round(float(p) * w * 100, 1) if has else None,
        })
    return out


def long_haul(od: pd.DataFrame, code: str, year: int, threshold: int) -> dict:
    """Share of departures on segments of at least `threshold` miles, for passenger and all-cargo service."""
    y = od[(od.year == year) & (od.origin == code)]

    def part(classes: set[str]) -> dict:
        d = y[y.svc_class.isin(classes)]
        total = float(d.departures.sum())
        lh = d[d.distance >= threshold]
        top = lh.groupby(["dest", "dest_country"]).departures.sum().sort_values(ascending=False).head(5)
        return {
            "departures": total,
            "long_haul_departures": float(lh.departures.sum()),
            "long_haul_share_pct": round(100 * float(lh.departures.sum()) / total, 1) if total else None,
            "top_long_haul_destinations": [{"dest": k[0], "country": k[1], "departures": float(v)} for k, v in top.items()],
        }

    return {
        "airport": code, "year": year, "threshold_miles": threshold,
        "passenger_service": part(config.PASSENGER_CLASSES),
        "all_cargo": part(config.CARGO_CLASSES),
        "definition": f"long haul = nonstop segment distance >= {threshold} statute miles (BTS great-circle); "
                      "shares are by departures performed",
    }


def unmet_demand(row: pd.Series, notes: dict, faa_entries: list, median_growth: float) -> dict:
    """Proxy flags for demand the airport cannot absorb. Spilled demand itself is not observable."""
    flags = {
        "full_flights": bool(pd.notna(row.load_factor) and row.load_factor >= config.UNMET["load_factor"]),
        "runway_constrained": bool(pd.notna(row.pct_runway_pressure) and row.pct_runway_pressure >= config.UNMET["pressure_pct"]),
        "growing": bool(pd.notna(row.growth_yoy) and row.growth_yoy > median_growth),
        "live_congestion": bool(faa_entries),
        "structural_constraint": any(n.get("type") == "constraint" for n in notes.get(row.name, [])),
    }
    n = sum(flags.values())
    return {
        "flags": flags,
        "flags_true": n,
        "level": "low" if n <= 1 else "moderate" if n <= 3 else "high",
        "thresholds": {"full_flights": f"load factor >= {config.UNMET['load_factor']:.0%}",
                       "runway_constrained": f"runway-pressure percentile >= {config.UNMET['pressure_pct']:.0%}",
                       "growing": f"passenger growth above the universe median ({median_growth:+.1%})",
                       "live_congestion": "FAA currently lists a delay, ground stop or closure",
                       "structural_constraint": "curated note of type 'constraint'"},
        "note": "Proxy signal - passengers who chose another airport or didn't fly are not observable in public data.",
    }


def select_states(region: str, states: list[str] | None) -> list[str]:
    """Named region wins over explicit states. Unknown region -> ValueError (tools turn it into an error dict)."""
    if region:
        if region not in config.REGIONS:
            raise ValueError(f"unknown region '{region}'; known regions: {', '.join(config.REGIONS)}")
        return config.REGIONS[region]
    return [s.upper() for s in (states or [])]


def jsonable(x):
    """Recursively convert numpy scalars, NaN and timestamps so json.dumps (and Gemini) accept the result."""
    if isinstance(x, dict):
        return {str(k): jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [jsonable(v) for v in x]
    if isinstance(x, (bool, np.bool_)):
        return bool(x)
    if isinstance(x, (int, np.integer)):
        return int(x)
    if isinstance(x, (float, np.floating)):
        return None if np.isnan(x) else float(x)
    if isinstance(x, pd.Timestamp):
        return str(x)
    return x
```

- [ ] **Step 4: Run the tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_metrics.py -q`
Expected: `9 passed`

- [ ] **Step 5: Commit**

```bash
git add metrics.py tests/test_metrics.py
git commit -m "Add score breakdown, long-haul share, unmet-demand signal and JSON helpers"
```

---

### Task 5: `live.py` — FAA NAS status and OpenSky

**Files:**
- Create: `live.py`, `tests/test_live.py`

**Interfaces:**
- Produces:
  - `live.parse_faa(xml_bytes: bytes) -> dict` → `{"updated": str, "entries": {ARPT: [ {"type": <Delay_type Name>, <child tag>: text | {attrs + grandchildren}} ]}}`
  - `live.faa_status() -> dict` (same shape, or `{"error": str}`), cached 60 s
  - `live.opensky_configured() -> bool`
  - `live.opensky_departures(icao: str) -> dict` → `{"status": "ok"|"not configured"|"unavailable"|"no icao", ...}`

FAA feed (verified 2026-10-18): root `AIRPORT_STATUS_INFORMATION` → `Update_Time`, repeated `Delay_type` blocks each with `Name` and a list (`Ground_Delay_List/Ground_Delay`, `Arrival_Departure_Delay_List/Delay`, `Airport_Closure_List/Airport`, `Ground_Stop_List/Program`); every record has an `ARPT` child. The parser is generic: any element with an `ARPT` child inside a `Delay_type` is a record.

- [ ] **Step 1: Write the failing tests**

`tests/test_live.py`:
```python
import live

SAMPLE = b"""<AIRPORT_STATUS_INFORMATION>
  <Update_Time>Sat Oct 18 12:00:00 2026 GMT</Update_Time>
  <Delay_type><Name>Ground Delay Programs</Name><Ground_Delay_List>
    <Ground_Delay><ARPT>AUS</ARPT><Reason>runway construction</Reason><Avg>39 minutes</Avg><Max>2 hours and 12 minutes</Max></Ground_Delay>
  </Ground_Delay_List></Delay_type>
  <Delay_type><Name>Ground Stop Programs</Name><Ground_Stop_List>
    <Program><ARPT>EWR</ARPT><Reason>WX:Thunderstorms</Reason><End_Time>5:00 pm EDT.</End_Time></Program>
  </Ground_Stop_List></Delay_type>
  <Delay_type><Name>General Arrival/Departure Delay Info</Name><Arrival_Departure_Delay_List>
    <Delay><ARPT>TEB</ARPT><Reason>VOL:Volume</Reason>
      <Arrival_Departure Type="Departure"><Min>16 minutes</Min><Max>30 minutes</Max><Trend>Increasing</Trend></Arrival_Departure>
    </Delay>
  </Arrival_Departure_Delay_List></Delay_type>
  <Delay_type><Name>Airport Closures</Name><Airport_Closure_List>
    <Airport><ARPT>LAX</ARPT><Reason>!LAX 10/123 LAX AD AP CLSD</Reason><Start>Oct 18 at 06:00 UTC.</Start><Reopen>Oct 18 at 13:00 UTC.</Reopen></Airport>
  </Airport_Closure_List></Delay_type>
</AIRPORT_STATUS_INFORMATION>"""


def test_parse_faa_collects_every_record_type():
    out = live.parse_faa(SAMPLE)
    assert out["updated"] == "Sat Oct 18 12:00:00 2026 GMT"
    assert set(out["entries"]) == {"AUS", "EWR", "TEB", "LAX"}
    assert out["entries"]["AUS"][0] == {"type": "Ground Delay Programs", "Reason": "runway construction",
                                        "Avg": "39 minutes", "Max": "2 hours and 12 minutes"}
    assert out["entries"]["EWR"][0]["type"] == "Ground Stop Programs"
    assert out["entries"]["TEB"][0]["Arrival_Departure"] == {"Type": "Departure", "Min": "16 minutes",
                                                              "Max": "30 minutes", "Trend": "Increasing"}
    assert out["entries"]["LAX"][0]["Reopen"] == "Oct 18 at 13:00 UTC."


def test_parse_faa_handles_empty_feed():
    assert live.parse_faa(b"<AIRPORT_STATUS_INFORMATION><Update_Time>x</Update_Time></AIRPORT_STATUS_INFORMATION>") == {
        "updated": "x", "entries": {}}


def test_opensky_not_configured(monkeypatch):
    monkeypatch.delenv("OPENSKY_CLIENT_ID", raising=False)
    monkeypatch.delenv("OPENSKY_CLIENT_SECRET", raising=False)
    assert live.opensky_configured() is False
    assert live.opensky_departures("KSFO")["status"] == "not configured"


def test_opensky_rejects_missing_icao(monkeypatch):
    monkeypatch.setenv("OPENSKY_CLIENT_ID", "x")
    monkeypatch.setenv("OPENSKY_CLIENT_SECRET", "y")
    assert live.opensky_departures(None)["status"] == "no icao"
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_live.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'live'`

- [ ] **Step 3: Write live.py**

```python
"""Live overlays: FAA NAS status (XML, no key) and OpenSky departures (optional OAuth2).

Nothing here is part of the score. Nothing here raises: failures come back as data so the
model can tell the user the signal is unavailable.
"""
from __future__ import annotations

import collections
import os
import time
import xml.etree.ElementTree as ET

import requests

FAA_URL = "https://nasstatus.faa.gov/api/airport-status-information"
OPENSKY_TOKEN_URL = "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token"
OPENSKY_API = "https://opensky-network.org/api"
TIMEOUT = 10
FAA_TTL = 60

_faa_cache = {"at": 0.0, "value": None}
_token = {"value": None, "expires": 0.0}


def parse_faa(xml_bytes: bytes) -> dict:
    """Every element with an ARPT child inside a Delay_type block is one record for that airport."""
    root = ET.fromstring(xml_bytes)
    entries: dict[str, list] = {}
    for block in root.findall("Delay_type"):
        kind = (block.findtext("Name") or block.tag).strip()
        for el in block.iter():
            if el.find("ARPT") is None:
                continue
            rec = {"type": kind}
            for child in el:
                if child.tag == "ARPT":
                    continue
                if len(child):   # e.g. <Arrival_Departure Type="Departure"><Min>..</Min>...</Arrival_Departure>
                    rec[child.tag] = {**child.attrib, **{g.tag: (g.text or "").strip() for g in child}}
                else:
                    rec[child.tag] = (child.text or "").strip()
            entries.setdefault(el.findtext("ARPT").strip(), []).append(rec)
    return {"updated": (root.findtext("Update_Time") or "").strip(), "entries": entries}


def faa_status() -> dict:
    """Current FAA delays/ground stops/closures for all airports; cached for FAA_TTL seconds."""
    if time.time() - _faa_cache["at"] < FAA_TTL and _faa_cache["value"] is not None:
        return _faa_cache["value"]
    try:
        r = requests.get(FAA_URL, timeout=TIMEOUT)
        r.raise_for_status()
        value = parse_faa(r.content)
    except Exception as e:  # network, HTTP, XML - all become "unavailable"
        value = {"error": f"FAA status unavailable: {e}"}
    _faa_cache.update(at=time.time(), value=value)
    return value


def opensky_configured() -> bool:
    return bool(os.environ.get("OPENSKY_CLIENT_ID") and os.environ.get("OPENSKY_CLIENT_SECRET"))


def _opensky_token() -> str:
    if _token["expires"] > time.time():
        return _token["value"]
    r = requests.post(OPENSKY_TOKEN_URL, timeout=TIMEOUT, data={
        "grant_type": "client_credentials",
        "client_id": os.environ["OPENSKY_CLIENT_ID"],
        "client_secret": os.environ["OPENSKY_CLIENT_SECRET"]})
    r.raise_for_status()
    j = r.json()
    _token.update(value=j["access_token"], expires=time.time() + j.get("expires_in", 1800) - 60)
    return _token["value"]


def opensky_departures(icao: str | None) -> dict:
    """Departures OpenSky recorded for the most recent complete UTC day (OpenSky publishes flights with ~1 day lag)."""
    if not opensky_configured():
        return {"status": "not configured",
                "hint": "set OPENSKY_CLIENT_ID and OPENSKY_CLIENT_SECRET (free account) to enable"}
    if not isinstance(icao, str) or len(icao) != 4:
        return {"status": "no icao", "icao": icao}
    end = int(time.time()) // 86400 * 86400      # 00:00 UTC today
    begin = end - 86400
    try:
        r = requests.get(f"{OPENSKY_API}/flights/departure", timeout=TIMEOUT,
                         params={"airport": icao, "begin": begin, "end": end},
                         headers={"Authorization": f"Bearer {_opensky_token()}"})
        if r.status_code == 404:      # OpenSky's way of saying "no flights in window"
            flights = []
        else:
            r.raise_for_status()
            flights = r.json()
    except Exception as e:
        return {"status": "unavailable", "error": str(e)}
    dests = collections.Counter((f.get("estArrivalAirport") or "unknown") for f in flights)
    return {"status": "ok", "icao": icao, "window_utc_epoch": [begin, end], "departures": len(flights),
            "top_destinations": [{"icao": k, "flights": v} for k, v in dests.most_common(5)],
            "caveat": "OpenSky coverage depends on volunteer receivers; counts are lower bounds."}
```

- [ ] **Step 4: Run the tests, then a real FAA call**

Run: `.venv/Scripts/python.exe -m pytest tests/test_live.py -q`
Expected: `4 passed`

Run: `.venv/Scripts/python.exe -c "import live; s=live.faa_status(); print(s.get('error') or (s['updated'], list(s['entries'])[:8]))"`
Expected: an update time and a list of airport codes (possibly empty on a quiet day), not an error.

- [ ] **Step 5: Commit**

```bash
git add live.py tests/test_live.py
git commit -m "Add FAA NAS status parser and optional OpenSky departures overlay"
```

---

### Task 6: Curated notes

**Files:**
- Create: `data/airport_notes.json`
- Modify: `tests/test_data_files.py` (append)

**Interfaces:**
- Produces: `data/airport_notes.json` = `{IATA: [{"type": "constraint"|"context", "text": str, "source": str, "verified": "YYYY-MM-DD"}]}`; read by `metrics.load()["notes"]`

Facts below were checked on 2026-10-18 against the listed sources. Before committing, open each source and confirm the numbers once more; fix the text if a source disagrees.

- [ ] **Step 1: Append the failing schema test**

Append to `tests/test_data_files.py`:
```python


def test_airport_notes_schema():
    import json
    notes = json.loads((DATA / "airport_notes.json").read_text(encoding="utf-8"))
    assert {"SNA", "SFO", "DCA", "ANC"} <= set(notes)
    for code, items in notes.items():
        assert code.isupper() and len(code) == 3
        for n in items:
            assert n["type"] in {"constraint", "context"}
            assert n["text"] and n["source"].startswith("https://") and n["verified"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_data_files.py -q -k notes`
Expected: FAIL — `FileNotFoundError`

- [ ] **Step 3: Write the notes file**

`data/airport_notes.json`:
```json
{
  "SNA": [
    {
      "type": "constraint",
      "text": "One commercial runway (20R/2L, about 5,700 ft) and the John Wayne Airport Settlement Agreement: annual passengers capped at 11.8 million through 2025 and 12.2 million for 2026-2030 (conditional), daily commercial departures limited, and no commercial departures 10 pm-7 am through 2035. Capacity here is legal before it is physical.",
      "source": "https://newportbeachca.gov/home/showpublisheddocument/58737/636565322849330000",
      "verified": "2026-10-18"
    }
  ],
  "SFO": [
    {
      "type": "constraint",
      "text": "Two pairs of parallel runways only 750 ft apart (independent parallel approaches need 4,300 ft). In 2025 the FAA banned side-by-side visual approaches, cutting the good-weather arrival rate from about 54 to about 36 per hour; low visibility already forced single-stream arrivals. Four runways behave like two for arrivals.",
      "source": "https://ops.group/blog/san-francisco-side-by-side-parallel-visual-approaches-banned/",
      "verified": "2026-10-18"
    }
  ],
  "DCA": [
    {
      "type": "constraint",
      "text": "Slot-controlled under the FAA High Density Rule (60 IFR operations per hour, 6 am-midnight) and a 1,250-statute-mile perimeter rule (49 U.S.C. 49109) with a small number of congressionally granted beyond-perimeter exemptions. Added capacity cannot be used without an act of Congress.",
      "source": "https://www.flyreagan.com/dca/dca-reagan-national-slot-perimeter-rules",
      "verified": "2026-10-18"
    }
  ],
  "ANC": [
    {
      "type": "context",
      "text": "World's #3 cargo airport in ACI's 2025 ranking (#4 in 2024) because roughly 80% of trans-Pacific freighters make a technical stop here to refuel and change crews. Most all-cargo departures are long-haul transit flights, not local demand; read the cargo long-haul share with that in mind.",
      "source": "https://www.alaskasnewssource.com/2026/04/19/ted-stevens-international-airport-now-ranks-1st-us-cargo-nears-top-worldwide-list/",
      "verified": "2026-10-18"
    }
  ]
}
```

- [ ] **Step 4: Run the tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_data_files.py -q`
Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add data/airport_notes.json tests/test_data_files.py
git commit -m "Add curated airport notes with sources"
```

---

### Task 7: `tools.py` — the six tools

**Files:**
- Create: `tools.py`, `tests/test_tools.py`

**Interfaces:**
- Consumes: `metrics.load, build_table, breakdown, long_haul, unmet_demand, select_states, jsonable`; `live.faa_status, opensky_departures`; `config.*`
- Produces (exact signatures — the docstrings become the schema Gemini sees, so keep them accurate):
  - `search_airports(query: str) -> dict`
  - `rank_airports(region: str = "", states: list[str] | None = None, top_n: int = 10) -> dict`
  - `airport_profile(code: str) -> dict`
  - `compare_airports(codes: list[str]) -> dict`
  - `long_haul_share(code: str, threshold_miles: int = 1500) -> dict`
  - `live_status(code: str) -> dict`
  - helpers `_table() -> tuple[pd.DataFrame, dict]` (cached), `_meta(t) -> dict`, `_methodology() -> dict`, `_row_summary(r, notes) -> dict`

pandas gotcha the implementer must respect: on a row `Series` `r`, `r.name` is the **index label** (the airport code) and `r.rank` is a **method**; always read columns with `r["name"]`, `r["rank"]`.

- [ ] **Step 1: Write the failing tests**

`tests/test_tools.py`:
```python
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
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_tools.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools'`

- [ ] **Step 3: Write tools.py**

```python
"""The six deterministic tools the model may call.

Every function returns a JSON-serializable dict, never raises, and carries `meta` + `caveats`
so the model can cite data year/source and state limits. Docstrings are the schema Gemini sees.
"""
from __future__ import annotations

import functools

import pandas as pd

import config
import live
import metrics


@functools.lru_cache(maxsize=1)
def _table() -> tuple[pd.DataFrame, dict]:
    d = metrics.load()
    return metrics.build_table(d["od"], d["airports"], d["runways"], config.YEARS[-1], config.YEARS[0]), d


def _meta(t: pd.DataFrame) -> dict:
    return {
        "data_year": config.YEARS[-1], "prior_year": config.YEARS[0],
        "source": "BTS T-100 Segment (All Carriers) via TranStats; OurAirports runways",
        "universe_size": int(t.in_universe.sum()),
    }


def _methodology() -> dict:
    return {
        "score": "Expansion Opportunity Score = 100 x sum(weight_i x percentile_rank_i); percentiles are taken "
                 "within the universe, so 85 means roughly top 15%",
        "weights": config.WEIGHTS,
        "universe": f"US airports with >= {config.UNIVERSE_MIN_PASSENGERS:,} originating passengers "
                    f"(passenger service, T-100 classes F+L) in {config.YEARS[-1]}",
        "runway_rule": f"runways counted when open and >= {config.MIN_RUNWAY_FT} ft",
        "runway_pressure": "departures of all service classes / 365 / counted runways",
        "not_in_score": "live FAA/OpenSky status (snapshot) and curated notes",
        "measures": "capacity-expansion opportunity, not profitability or ROI",
    }


def _pct(x) -> float | None:
    return None if pd.isna(x) else round(float(x) * 100, 1)


def _caveats(r: pd.Series) -> list[str]:
    c = []
    if pd.isna(r["runways"]):
        c.append("No runway data matched in OurAirports; runway pressure excluded and weights renormalized.")
    if pd.isna(r["growth_yoy"]):
        c.append(f"No {config.YEARS[0]} data; growth excluded and weights renormalized.")
    if not r["in_universe"]:
        c.append(f"Below the universe threshold ({config.UNIVERSE_MIN_PASSENGERS:,} passengers); no score or percentiles.")
    return c


def _row_summary(r: pd.Series, notes: dict) -> dict:
    code = r.name   # index label, not the "name" column
    return {
        "code": code, "name": r["name"], "city": r["municipality"], "state": r["state"],
        "score": r["score"], "national_rank": r["rank"],
        "passengers": r["passengers"], "load_factor_pct": _pct(r["load_factor"]),
        "departures_passenger_service": r["departures"], "departures_all_classes": r["departures_all"],
        "runways": r["runways"], "departures_per_runway_per_day": r["runway_pressure"],
        "growth_yoy_pct": _pct(r["growth_yoy"]), "intl_share_pct": _pct(r["intl_share"]),
        "avg_stage_length_mi": r["avg_stage_mi"],
        "breakdown": metrics.breakdown(r),
        "curated_notes": notes.get(code, []),
        "caveats": _caveats(r),
    }


def search_airports(query: str) -> dict:
    """Find airports in the ranking universe by IATA code, airport name or city. Use when unsure of a code.

    Args:
        query: free text such as "Santa Ana", "Logan", "SNA"
    """
    t, _ = _table()
    q = query.strip().lower()
    u = t[t.in_universe]
    hit = u[(u.index.str.lower() == q)
            | u["name"].fillna("").str.lower().str.contains(q, regex=False)
            | u["municipality"].fillna("").str.lower().str.contains(q, regex=False)]
    matches = [{"code": c, "name": r["name"], "city": r["municipality"], "state": r["state"]} for c, r in hit.head(10).iterrows()]
    return metrics.jsonable({"query": query, "matches": matches, "meta": _meta(t),
                             "hint": "" if matches else "no match in the universe; the airport may be too small or spelled differently"})


def rank_airports(region: str = "", states: list[str] | None = None, top_n: int = 10) -> dict:
    """Rank US airports by Expansion Opportunity Score (0-100), optionally filtered to a region or states.

    Args:
        region: new_england, mid_atlantic, southeast, midwest, texas, mountain_west, west_coast, pacific_northwest or alaska_hawaii; empty string for the whole US
        states: two-letter state codes such as ["MA", "CT"]; used only when region is empty
        top_n: number of airports to return (1-50)
    """
    t, d = _table()
    try:
        sel = metrics.select_states(region, states)
    except ValueError as e:
        return {"error": str(e), "regions": list(config.REGIONS)}
    u = t[t.in_universe]
    if sel:
        u = u[u.state.isin(sel)]
    matching = int(len(u))
    u = u.sort_values("score", ascending=False).head(max(1, min(int(top_n), 50)))
    return metrics.jsonable({
        "filter": {"region": region or None, "states": sel or None},
        "airports_matching_filter": matching,
        "ranking": [_row_summary(r, d["notes"]) for _, r in u.iterrows()],
        "methodology": _methodology(), "meta": _meta(t),
        "caveats": ["Score measures capacity-expansion opportunity from public traffic and runway data; it is not an ROI estimate.",
                    "Weights are analyst judgment, not fitted to outcomes."],
    })


def airport_profile(code: str) -> dict:
    """Full profile of one airport: metrics, score breakdown, unmet-demand signal, curated notes and live status.

    Args:
        code: IATA code such as "SFO"
    """
    t, d = _table()
    code = code.strip().upper()
    if code not in t.index:
        return {"error": f"{code} not found in T-100 data", "hint": "use search_airports to find the code"}
    r = t.loc[code]
    out = _row_summary(r, d["notes"])
    out["live"] = live_status(code)
    out["unmet_demand"] = metrics.unmet_demand(r, d["notes"], out["live"]["faa"]["entries"],
                                               float(t[t.in_universe].growth_yoy.median()))
    out["methodology"] = _methodology()
    out["meta"] = _meta(t)
    return metrics.jsonable(out)


def compare_airports(codes: list[str]) -> dict:
    """Compare 2-5 airports side by side on every metric, score breakdown, unmet-demand signal and live status.

    Args:
        codes: IATA codes such as ["LAX", "SNA"]
    """
    codes = [c.strip().upper() for c in codes]
    if not 2 <= len(codes) <= 5:
        return {"error": "give between 2 and 5 airport codes"}
    profiles = [airport_profile(c) for c in codes]
    bad = [p for p in profiles if "error" in p]
    if bad:
        return {"error": "; ".join(p["error"] for p in bad), "hint": "use search_airports to find the code"}
    t, _ = _table()
    for p in profiles:
        p.pop("methodology", None)
        p.pop("meta", None)
    return metrics.jsonable({"airports": profiles, "methodology": _methodology(), "meta": _meta(t),
                             "caveats": ["Higher departures per runway per day = more congested relative to physical capacity.",
                                         "Live status is a snapshot at query time and is not part of the score."]})


def long_haul_share(code: str, threshold_miles: int = config.LONG_HAUL_MILES) -> dict:
    """Share of an airport's departures that are long haul, for passenger service and all-cargo service separately.

    Args:
        code: IATA code such as "ANC"
        threshold_miles: nonstop segment distance that counts as long haul (default 1500 statute miles)
    """
    t, d = _table()
    code = code.strip().upper()
    if code not in t.index:
        return {"error": f"{code} not found in T-100 data", "hint": "use search_airports to find the code"}
    out = metrics.long_haul(d["od"], code, config.YEARS[-1], int(threshold_miles))
    out["curated_notes"] = d["notes"].get(code, [])
    out["meta"] = _meta(t)
    out["caveats"] = ["The threshold is an assumption; 1,500 mi is roughly a 3.5-hour flight. Ask for another threshold if needed.",
                      "Shares are by departures performed, not by seats or passengers."]
    return metrics.jsonable(out)


def live_status(code: str) -> dict:
    """Current FAA delay/ground-stop/closure status for an airport and, if configured, yesterday's OpenSky departure count.

    Args:
        code: IATA code such as "EWR"
    """
    t, _ = _table()
    code = code.strip().upper()
    faa = live.faa_status()
    icao = t.icao.get(code) if code in t.index else None
    return metrics.jsonable({
        "airport": code,
        "faa": {"updated": faa.get("updated"), "entries": faa.get("entries", {}).get(code, []), "error": faa.get("error")},
        "opensky": live.opensky_departures(icao),
        "caveats": ["FAA status is a snapshot at query time, not history; an empty list means no current FAA advisory."],
    })
```

- [ ] **Step 4: Run the tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_tools.py -q`
Expected: `6 passed`

- [ ] **Step 5: Smoke-test against real data (no LLM yet)**

Run: `.venv/Scripts/python.exe -c "import json, tools; r = tools.rank_airports(region='new_england'); print(json.dumps([(a['code'], a['score'], a['runways'], a['load_factor_pct']) for a in r['ranking']])); print(r['meta'])"`
Expected: six New England airports (BOS, BDL, PVD, MHT, PWM, BTV in some order) with scores between 0 and 100, and `universe_size` around 100–130.

- [ ] **Step 6: Commit**

```bash
git add tools.py tests/test_tools.py
git commit -m "Add the six deterministic agent tools"
```

---

### Task 8: Integration sanity tests on the real data

**Files:**
- Create: `tests/test_integration_real_data.py`

**Interfaces:**
- Consumes: `tools.*`, `metrics.*`, real `data/`

These assert things that must hold for the data to be trustworthy — not the ranking order, which is a judgment the score encodes.

- [ ] **Step 1: Write the tests**

`tests/test_integration_real_data.py`:
```python
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


def test_every_tool_result_is_json():
    for r in (tools.rank_airports(top_n=50), tools.airport_profile("BOS"), tools.compare_airports(["LAX", "SNA"]),
              tools.long_haul_share("ANC"), tools.live_status("SFO"), tools.search_airports("Santa Ana")):
        json.dumps(r)
```

- [ ] **Step 2: Run them**

Run: `.venv/Scripts/python.exe -m pytest tests/test_integration_real_data.py -q`
Expected: `6 passed`. If `LAX runways == 4` fails, inspect `data/runways_us.csv` for `KLAX` (expected four ≥ 5,000 ft, closed = 0) and adjust the assertion only if OurAirports really lists a different count.

- [ ] **Step 3: Run the whole suite and commit**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: all passed, 0 skipped.

```bash
git add tests/test_integration_real_data.py
git commit -m "Add real-data sanity tests"
```

---

### Task 9: `agent.py` — Gemini tool loop and CLI smoke test

**Files:**
- Create: `agent.py`, `tests/test_agent.py`

**Interfaces:**
- Consumes: `tools.search_airports, rank_airports, airport_profile, compare_airports, long_haul_share, live_status`; `config.MODEL`
- Produces:
  - `agent.TOOLS: list[callable]`, `agent.SYSTEM_PROMPT: str`
  - `agent.ask(history: list, text: str, max_iterations: int = 6) -> tuple[str, list[dict], list]` — `(answer, trace, new_history)`; trace items `{"tool": str, "args": dict, "result": dict}`
  - `agent.transcribe(audio_bytes: bytes, mime_type: str) -> str`
  - `python agent.py "<question>"` prints trace and answer

Verified against google-genai 2.31.0 on 2026-10-18: passing Python functions in `GenerateContentConfig.tools` generates schemas from type hints and docstrings (`list[str] | None` → nullable ARRAY, defaults kept); `AutomaticFunctionCallingConfig(disable=True)` leaves `response.function_calls` for us; `types.Part.from_function_response(name=, response=)` and `types.Content(role="tool", parts=[...])` build the reply.

- [ ] **Step 1: Write the failing test (loop logic with a fake client; no network)**

`tests/test_agent.py`:
```python
import types as pytypes

from google.genai import types

import agent


class FakeResponse:
    def __init__(self, text=None, calls=None):
        self.text = text
        self.function_calls = calls or []
        part = types.Part.from_text(text=text) if text else types.Part.from_function_call(name=calls[0].name, args=calls[0].args)
        self.candidates = [pytypes.SimpleNamespace(content=types.Content(role="model", parts=[part]))]


def test_ask_runs_tool_then_returns_text(monkeypatch):
    calls = [FakeResponse(calls=[types.FunctionCall(name="rank_airports", args={"region": "new_england", "top_n": 3})]),
             FakeResponse(text="BOS leads.")]
    monkeypatch.setattr(agent, "_generate", lambda client, history: calls.pop(0))
    monkeypatch.setattr(agent, "_client", lambda: None)
    monkeypatch.setitem(agent._BY_NAME, "rank_airports", lambda **kw: {"ranking": [{"code": "BOS"}], "args_seen": kw})
    answer, trace, history = agent.ask([], "New England candidates?")
    assert answer == "BOS leads."
    assert trace == [{"tool": "rank_airports", "args": {"region": "new_england", "top_n": 3},
                      "result": {"ranking": [{"code": "BOS"}], "args_seen": {"region": "new_england", "top_n": 3}}}]
    assert [c.role for c in history] == ["user", "model", "tool", "model"]
    assert history[2].parts[0].function_response.name == "rank_airports"


def test_tool_exception_is_returned_to_model_not_raised(monkeypatch):
    calls = [FakeResponse(calls=[types.FunctionCall(name="airport_profile", args={"code": "SFO"})]),
             FakeResponse(text="Sorry, that failed.")]
    monkeypatch.setattr(agent, "_generate", lambda client, history: calls.pop(0))
    monkeypatch.setattr(agent, "_client", lambda: None)

    def boom(**kw):
        raise RuntimeError("disk on fire")
    monkeypatch.setitem(agent._BY_NAME, "airport_profile", boom)
    answer, trace, _ = agent.ask([], "SFO?")
    assert trace[0]["result"] == {"error": "RuntimeError: disk on fire"} and answer == "Sorry, that failed."


def test_iteration_cap(monkeypatch):
    monkeypatch.setattr(agent, "_generate", lambda client, history: FakeResponse(
        calls=[types.FunctionCall(name="live_status", args={"code": "SFO"})]))
    monkeypatch.setattr(agent, "_client", lambda: None)
    monkeypatch.setitem(agent._BY_NAME, "live_status", lambda **kw: {"ok": True})
    answer, trace, _ = agent.ask([], "loop", max_iterations=3)
    assert len(trace) == 3 and "ran out" in answer
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_agent.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent'`

- [ ] **Step 3: Write agent.py**

```python
"""Gemini tool-calling loop. The model picks tools and narrates; it never computes a number.

Automatic function calling is disabled on purpose: running the loop ourselves gives the UI a
complete trace of every call and result, and turns tool exceptions into data the model can explain.
"""
from __future__ import annotations

import os
import time

from google import genai
from google.genai import errors, types

import config
import tools

TOOLS = [tools.search_airports, tools.rank_airports, tools.airport_profile,
         tools.compare_airports, tools.long_haul_share, tools.live_status]
_BY_NAME = {f.__name__: f for f in TOOLS}

SYSTEM_PROMPT = """You are the Airport Investment Intelligence Agent: an analyst assistant for a firm that invests in US airport modernization. You help analysts find airports where added flight and passenger capacity would be most valuable, and you explain why.

Hard rules:
1. Every number, ranking or airport fact you state must come from a tool result in this conversation. If you have not called a tool for it, call one. Never recall or estimate figures.
2. Resolve airport names to IATA codes. For ambiguous city names use the primary commercial airport and say which you chose ("LA" -> LAX, "Santa Ana" -> SNA, "Anchorage" -> ANC, "Boston" -> BOS). When unsure, call search_airports.
3. Named regions you can pass to rank_airports: new_england, mid_atlantic, southeast, midwest, texas, mountain_west, west_coast, pacific_northwest, alaska_hawaii. For anything else pass explicit two-letter states.
4. Answer structure: (a) the direct answer in one or two sentences; (b) a compact markdown table of the key numbers; (c) the reasoning, built from the score breakdown (component, percentile, weight, contribution) or the unmet-demand flags; (d) a short "Assumptions & caveats" list: data year and source from meta, every caveat the tool returned, and that the score measures capacity-expansion opportunity, not profitability.
5. Report percentages exactly as the *_pct fields give them (one decimal). Do not do arithmetic beyond comparing numbers.
6. Curated notes are hand-written context with a source; say "curated note" when you use one. Live status (FAA, OpenSky) is a snapshot and is never part of the score; say so when you mention it.
7. Follow-up questions refer to the airports and filters already discussed unless the user says otherwise.
8. If a tool returns an error, explain it plainly and suggest what to ask instead.
Be concise and specific. No marketing language."""


def _client() -> genai.Client:
    return genai.Client(api_key=os.environ["GEMINI_API_KEY"])


def _config() -> types.GenerateContentConfig:
    return types.GenerateContentConfig(
        tools=TOOLS,
        system_instruction=SYSTEM_PROMPT,
        temperature=0.2,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )


def _generate(client: genai.Client, history: list):
    """One model call with retries on rate limit / overload."""
    for attempt in range(3):
        try:
            return client.models.generate_content(model=config.MODEL, contents=history, config=_config())
        except errors.APIError as e:
            if getattr(e, "code", None) in (429, 503) and attempt < 2:
                time.sleep(2 * 2 ** attempt)
                continue
            raise


def ask(history: list, text: str, max_iterations: int = 6) -> tuple[str, list[dict], list]:
    """Send one user turn. Returns (answer_text, tool_trace, updated_history)."""
    client = _client()
    history = history + [types.Content(role="user", parts=[types.Part.from_text(text=text)])]
    trace: list[dict] = []
    for _ in range(max_iterations):
        response = _generate(client, history)
        if not response.candidates:
            return "The model returned no answer (safety filter or empty response). Please rephrase.", trace, history
        history.append(response.candidates[0].content)
        if not response.function_calls:
            return response.text or "", trace, history
        parts = []
        for call in response.function_calls:
            args = dict(call.args or {})
            try:
                result = _BY_NAME[call.name](**args)
            except Exception as e:   # the model gets the error as data and can recover or explain
                result = {"error": f"{type(e).__name__}: {e}"}
            trace.append({"tool": call.name, "args": args, "result": result})
            parts.append(types.Part.from_function_response(name=call.name, response={"result": result}))
        history.append(types.Content(role="tool", parts=parts))
    return "I ran out of tool-call iterations; please narrow the question.", trace, history


def transcribe(audio_bytes: bytes, mime_type: str = "audio/wav") -> str:
    """Speech to text with the same model (voice input bonus)."""
    r = _client().models.generate_content(
        model=config.MODEL,
        contents=[types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
                  "Transcribe this audio verbatim. Return only the transcript."])
    return (r.text or "").strip()


if __name__ == "__main__":
    import sys

    from dotenv import load_dotenv

    load_dotenv()
    answer, trace, _ = ask([], " ".join(sys.argv[1:]) or "Compare LA and Santa Ana airport congestion levels.")
    for t in trace:
        print(f"[tool] {t['tool']}({t['args']})")
    print(answer)
```

- [ ] **Step 4: Run the unit tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_agent.py -q`
Expected: `3 passed`

- [ ] **Step 5: Create `.env` and smoke-test the four assignment questions (needs the key)**

Copy `.env.example` to `.env` and put the Gemini key in it (the key never goes into chat or git). Then:

```bash
.venv/Scripts/python.exe agent.py "Which airports in New England are strong candidates for terminal expansion?"
.venv/Scripts/python.exe agent.py "Compare LA and Santa Ana airport congestion levels."
.venv/Scripts/python.exe agent.py "What is the percentage of long haul flights out of Anchorage airport?"
.venv/Scripts/python.exe agent.py "What is the unmet flight demand in SFO airport and why?"
```
Expected for each: one or two `[tool] ...` lines (`rank_airports(region='new_england')`, `compare_airports(codes=['LAX','SNA'])`, `long_haul_share(code='ANC')`, `airport_profile(code='SFO')`) and an answer with a table, reasoning from the breakdown/flags, and an "Assumptions & caveats" section. If the model answers without calling a tool, strengthen rule 1 in `SYSTEM_PROMPT` ("Call a tool before answering any question about an airport") and rerun. If it mis-maps a region, add the example to rule 3.

- [ ] **Step 6: Commit**

```bash
git add agent.py tests/test_agent.py
git commit -m "Add Gemini tool-calling agent loop and CLI"
```

---

### Task 10: `app.py` — Streamlit chat

**Files:**
- Create: `app.py`

**Interfaces:**
- Consumes: `agent.ask`, `agent.transcribe`, `tools._table`, `tools._meta`, `config.*`, `live.opensky_configured`
- Produces: `streamlit run app.py` on http://localhost:8501; `render_trace(trace: list[dict])`

- [ ] **Step 1: Write app.py**

```python
"""Streamlit chat UI. All intelligence is in agent.py / tools.py; this file only renders."""
import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

import agent    # noqa: E402  (after load_dotenv so GEMINI_API_KEY is visible)
import config   # noqa: E402
import live     # noqa: E402
import tools    # noqa: E402

st.set_page_config(page_title="Airport Investment Intelligence", page_icon="✈️", layout="wide")

EXAMPLES = [
    "Which airports in New England are strong candidates for terminal expansion?",
    "Compare LA and Santa Ana airport congestion levels.",
    "What is the percentage of long haul flights out of Anchorage airport?",
    "What is the unmet flight demand in SFO airport and why?",
]

if not os.environ.get("GEMINI_API_KEY"):
    st.error("GEMINI_API_KEY is not set. Copy .env.example to .env and add a free key from https://aistudio.google.com/apikey")
    st.stop()
try:
    table, _ = tools._table()
except FileNotFoundError:
    st.error("Data files are missing. Run:  python scripts/fetch_data.py")
    st.stop()

ss = st.session_state
ss.setdefault("history", [])    # Gemini contents
ss.setdefault("messages", [])   # what we render


def render_trace(trace: list[dict]) -> None:
    """The deterministic data behind an answer: every tool call with its arguments and result."""
    if not trace:
        return
    with st.expander(f"Data behind this answer · {len(trace)} tool call(s)"):
        for t in trace:
            args = ", ".join(f"{k}={v!r}" for k, v in t["args"].items())
            st.markdown(f"`{t['tool']}({args})`")
            res = t["result"]
            rows = res.get("ranking") or res.get("airports") if isinstance(res, dict) else None
            if rows:
                df = pd.DataFrame(rows)
                flat = [c for c in df.columns if not df[c].map(lambda v: isinstance(v, (dict, list))).any()]
                st.dataframe(df[flat], hide_index=True)
            st.json(res, expanded=False)


with st.sidebar:
    st.header("How the score works")
    meta = tools._meta(table)
    st.markdown(
        f"**Expansion Opportunity Score** = 100 × Σ weight × percentile rank, computed within "
        f"{meta['universe_size']} US airports with ≥ {config.UNIVERSE_MIN_PASSENGERS:,} originating passengers in {config.YEARS[-1]}.")
    st.table(pd.Series(config.WEIGHTS, name="weight"))
    st.caption(
        f"Data: BTS T-100 {config.YEARS[0]}–{config.YEARS[-1]} · OurAirports runways (≥ {config.MIN_RUNWAY_FT:,} ft) · "
        f"FAA NAS status (live) · OpenSky ({'configured' if live.opensky_configured() else 'not configured'})")
    st.caption("Live signals are shown next to the score, never inside it. The score measures capacity-expansion "
               "opportunity, not profitability.")
    st.subheader("Try")
    for q in EXAMPLES:
        if st.button(q):
            ss.pending = q
    if st.button("Clear chat"):
        ss.history, ss.messages = [], []
        st.rerun()

st.title("✈️ Airport Investment Intelligence Agent")
st.caption("Deterministic scoring over public aviation data; the model only routes questions to tools and explains the results.")

for m in ss.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])
        render_trace(m.get("trace", []))

prompt = st.chat_input("Ask about US airport capacity, congestion or demand…") or ss.pop("pending", None)
if prompt:
    ss.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        with st.spinner("Querying data…"):
            try:
                answer, trace, ss.history = agent.ask(ss.history, prompt)
            except Exception as e:   # model/network failure: show it, keep the chat alive
                answer, trace = f"The model call failed: {e}. Check the API key and try again in a minute.", []
        st.markdown(answer)
        render_trace(trace)
    ss.messages.append({"role": "assistant", "content": answer, "trace": trace})
```

- [ ] **Step 2: Run it and exercise the four examples**

Run: `.venv/Scripts/python.exe -m streamlit run app.py --server.headless true`
Open http://localhost:8501. Click each example button in turn; confirm each answer renders with the "Data behind this answer" expander showing the tool call and a table. Ask one follow-up ("and how does PVD compare to BDL?") to confirm conversation memory. Save four screenshots to `docs/screenshots/q1.png` … `q4.png` (used by README).

Expected: no tracebacks in the terminal; each answer cites the data year and ends with caveats.

- [ ] **Step 3: Commit**

```bash
git add app.py docs/screenshots/
git commit -m "Add Streamlit chat UI with tool trace"
```

---

### Task 11: `DESIGN.md` and `README.md`

**Files:**
- Create: `DESIGN.md`, `README.md`

- [ ] **Step 1: Write DESIGN.md**

```markdown
# Design — Airport Investment Intelligence Agent

## 1. Purpose and framing

We invest in US airport modernization. The agent helps an analyst find airports where added flight and
passenger capacity would be most valuable, and explains why with numbers the analyst can audit.

Three principles drive the design:

1. **Numbers come from deterministic code over public data.** The language model never calculates a metric.
2. **The model does two jobs:** translate a question into tool calls, and narrate the tool results — including
   the caveats the tools return.
3. **The score measures capacity-expansion *opportunity*, not profitability.** Public data carries no CAPEX,
   land, financing or politics, so the agent says so in every answer.

## 2. Scoring methodology

### 2.1 Universe
US airports with at least 500,000 originating passengers (passenger service) in the latest complete T-100
year (2025). This keeps the ~110 airports where a terminal or airfield program is plausible, including the
smaller New England hubs (PVD, MHT, PWM, BTV), while excluding general-aviation noise. Airports below the
threshold still get metrics, but no score — percentiles against the universe would be misleading.

### 2.2 Metrics (per airport, latest year)

| Metric | Definition | Why it matters |
|---|---|---|
| passengers, seats, departures | sums over segments departing the airport, passenger service (T-100 classes F + L) | demand volume |
| load factor | passengers / seats | full aircraft = demand airlines cannot add seats for |
| departures (all classes) | including all-cargo (G + P) — freighters consume runway slots too | runway demand |
| runways | OurAirports runways that are open and ≥ 5,000 ft | commercial-capable physical capacity |
| runway pressure | departures (all classes) / 365 / runways | departures per runway per day — the bottleneck proxy |
| growth | passengers latest / passengers prior − 1 (2025 vs 2024) | direction of travel |
| average stage length, international share, long-haul share | distance-weighted by departures | network character; answers "how long-haul is this airport?" |

### 2.3 Expansion Opportunity Score (0–100)

    score = 100 × Σ weightᵢ × percentile_rankᵢ        (percentiles within the universe)

| Component | Weight | Rationale |
|---|---|---|
| runway pressure | 0.35 | the most direct public signal of a physical bottleneck |
| passengers | 0.25 | market size — expansion needs someone to serve |
| load factor | 0.25 | full aircraft mean demand is being rationed |
| growth | 0.15 | investment is on the future, not the present |

Design decisions:
- **Percentile rank, not min–max.** Robust to ATL/LAX outliers, and "score 85" reads as "top 15%". Percentile
  ranking is invariant to monotonic transforms, so no log on passengers is needed.
- **Missing components drop out and the remaining weights renormalize**, with a caveat in the result, instead of
  silently scoring zero.
- **Live signals are not in the score.** A ranking that changes with the weather is not a ranking. FAA status and
  OpenSky counts are shown next to the score as a "right now" overlay.
- **Weights are analyst judgment, not fitted.** There is no public ground truth for "profitable renovation". They
  live in `config.py`, and every result returns a breakdown (component, percentile, weight, contribution) so a
  reader can disagree with a weight and still use the numbers.

### 2.4 Unmet-demand signal (a proxy, labeled as such)
Five flags with thresholds in `config.py`: full flights (load factor ≥ 85%), runway-constrained (pressure
percentile ≥ 80%), growing faster than the universe median, live FAA congestion, structural constraint (curated
note). 0–1 flags = low, 2–3 = moderate, 4–5 = high. Every result repeats: passengers who chose another airport
or did not fly are not observable in public data.

### 2.5 Long-haul share
Share of departures on nonstop segments of at least 1,500 statute miles (configurable per question), reported
separately for passenger and all-cargo service — at Anchorage the two tell opposite stories.

### 2.6 Worked example
(Paste the New England ranking table from the app here, with the date it was generated.)

## 3. Data sources and their limits

| Source | What we use | How | Limits |
|---|---|---|---|
| BTS T-100 Segment (All Carriers) | per-segment departures, seats, passengers, distance, service class, 2024–2025 | `scripts/fetch_data.py` replays the TranStats download form (no stable URL exists); the annual aggregate is committed so reviewers need no download | 3–6 month publication lag; annual aggregation hides seasonality |
| OurAirports | runway length/status, coordinates, ICAO codes | public-domain CSV | runway count ignores spacing, taxiways, gates — see curated notes |
| FAA NAS Status | current ground delays, ground stops, closures | public XML, no key | snapshot only, no history |
| OpenSky Network (optional) | yesterday's departures per airport | REST + OAuth2, free account | volunteer-receiver coverage; counts are lower bounds |
| Curated notes | four verified structural facts (SNA cap, SFO runway spacing, DCA slots/perimeter, ANC cargo stop) | hand-written JSON with source URLs, shown as "curated note" | small by design; a reviewer can see exactly what human knowledge was injected |

## 4. Where AI is used — and where it is deliberately not

**Used:** Gemini (`gemini-3.8-flash`, free tier, via `google-genai`) maps the question to one of six tools and
their arguments, narrates the result, keeps conversational context for follow-ups, and (bonus) transcribes
voice input.

**Not used:** every metric, percentile, score, flag and ranking is computed in `metrics.py` and `tools.py`;
`pytest` covers them with synthetic data where the expected numbers are worked out by hand.

**Guardrails:** automatic function calling is disabled and the loop is ours, so the UI shows every tool call and
result under each answer ("Data behind this answer"); tool exceptions go back to the model as data; the system
prompt forbids numbers that did not come from a tool and requires an "Assumptions & caveats" section;
temperature 0.2.

## 5. Key tradeoffs

- **Replayed bulk download vs. a live API for traffic data.** Depth (seats, distance, class) was worth more than
  liveness; BTS has no REST endpoint; liveness comes from FAA/OpenSky instead.
- **Committed processed data vs. fetching at run time.** One command runs the app; refresh is a script.
- **Annual vs. monthly.** Seasonality is lost; the data stays under 2 MB and the ranking is stable.
- **Runway count as the capacity proxy.** The only public, structured one. Its blind spots (SFO's 750 ft runway
  spacing, SNA's legal cap) are covered by labeled curated notes rather than hidden heuristics.
- **Manual tool loop vs. SDK automatic function calling.** About 25 extra lines buy a visible trace and controlled
  error handling — the trace is the "explain your reasoning" feature.
- **Free Gemini tier.** No cost, native function calling; a question costs at most three model calls.

## 6. How assumptions, uncertainty and scope reach the user

Every tool result carries `meta` (data year, source, universe size) and `caveats`; the prompt makes the model
repeat them. Live sources degrade to an explicit "unavailable"/"not configured" rather than a silent zero. Airports
below the universe threshold get metrics but `score: null` and a caveat. Curated notes are labeled with their
source. The sidebar states the formula, the weights and what the score does not measure.

## 7. Limitations and next steps

Gate and terminal-area data (FAA ADIP) would turn "terminal expansion" from inference into measurement;
FAA ASPM would add delay history; monthly data would expose seasonal peaks; a cost layer (construction index,
land) would move the score toward ROI; a weight-sensitivity view in the UI would let analysts stress-test the
ranking; an evaluation set of analyst questions with expected tool calls would guard the prompt.
```

Then replace the placeholder line in 2.6 with the actual New England ranking table copied from the app's trace expander (code, score, passengers, load factor %, runways, departures/runway/day, growth %), and the date.

- [ ] **Step 2: Write README.md**

```markdown
# Airport Investment Intelligence Agent

Chat with an agent that ranks and explains US airports as capacity-expansion investment opportunities.
Deterministic scoring over BTS T-100 traffic and OurAirports runway data, a live FAA (and optional OpenSky)
overlay, and Gemini used only to route questions to tools and explain the results. See `DESIGN.md` for the
methodology and tradeoffs.

## Quick start

    python -m venv .venv
    .venv\Scripts\activate            # Windows   |   source .venv/bin/activate on macOS/Linux
    pip install -r requirements.txt
    copy .env.example .env            # then put your free Gemini key in .env (https://aistudio.google.com/apikey)
    streamlit run app.py

Data for 2024–2025 is committed, so no download is needed. To refresh it (BTS publishes with a lag):

    python scripts/fetch_data.py

Optional live departures from OpenSky: create a free API client at https://opensky-network.org and set
`OPENSKY_CLIENT_ID` / `OPENSKY_CLIENT_SECRET` in `.env`.

## Try asking

- Which airports in New England are strong candidates for terminal expansion?
- Compare LA and Santa Ana airport congestion levels.
- What is the percentage of long haul flights out of Anchorage airport?
- What is the unmet flight demand in SFO airport and why?
- …and follow-ups: "and PVD vs BDL?", "use 2,500 miles as the long-haul threshold".

Under every answer, "Data behind this answer" shows each tool call and its full result.

## Command line

    python agent.py "Compare LA and Santa Ana airport congestion levels."

## Tests

    pytest

Unit tests use a synthetic three-airport dataset with hand-computed expected values; `tests/test_integration_real_data.py`
checks the committed data for plausibility (universe size, SFO load factor, SNA runway count, ANC cargo vs passenger long-haul).

## Layout

    app.py                 Streamlit chat
    agent.py               Gemini tool loop (manual, with trace)
    tools.py               the six deterministic tools
    metrics.py             per-airport table, score, breakdown, long-haul, unmet-demand
    live.py                FAA NAS status, OpenSky
    config.py              every tunable
    scripts/fetch_data.py  builds data/ from BTS TranStats + OurAirports
    data/                  committed extracts + curated notes
    tests/
    DESIGN.md              scoring methodology, tradeoffs, where AI is used

## Screenshots

![New England ranking](docs/screenshots/q1.png)
![LAX vs SNA](docs/screenshots/q2.png)
```

- [ ] **Step 3: Run the full suite once more and commit**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: all passed.

```bash
git add DESIGN.md README.md
git commit -m "Add design document and README"
```

---

### Task 12 (bonus, only if time remains): voice input

**Files:**
- Modify: `app.py` (insert before the `prompt = st.chat_input(...)` line)

**Interfaces:**
- Consumes: `agent.transcribe(audio_bytes, mime_type)`

- [ ] **Step 1: Add the audio widget**

Insert into `app.py` immediately above `prompt = st.chat_input(...)`:
```python
audio = st.audio_input("Or ask by voice")
if audio is not None and audio.getvalue() != ss.get("last_audio"):
    ss.last_audio = audio.getvalue()                 # the widget keeps returning the same clip; send it once
    with st.spinner("Transcribing…"):
        ss.pending = agent.transcribe(ss.last_audio, audio.type or "audio/wav")
```

- [ ] **Step 2: Try it**

Run: `.venv/Scripts/python.exe -m streamlit run app.py --server.headless true`
Record "compare LA and Santa Ana airport congestion levels"; the transcript appears as the user message and the agent answers.
Expected: transcript matches; the same clip is not re-sent on later reruns.

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "Add voice input via Gemini transcription"
```

---

## Self-review against the spec

- Spec §2 scope (universe, question types, chat, follow-ups, deliverables): Tasks 7, 9, 10, 11. Voice bonus: Task 12.
- Spec §3 data sources: T-100 FMG + OurAirports (Task 2), FAA + OpenSky (Task 5), curated notes (Task 6).
- Spec §4 metrics incl. NaN handling: Tasks 3–4 (`build_table`, `score` renormalization, `_caveats`).
- Spec §5 score, percentile ranking, live-out-of-score, breakdown, unmet-demand flags/levels/sentence: Tasks 3, 4, 7.
- Spec §6 six tools with exact signatures, `meta` + `caveats`, unknown-code error with hint, below-universe `score = None`: Task 7. Agent loop, retries, system prompt rules: Task 9. UI sidebar/expander/example buttons/clear: Task 10.
- Spec §7 error handling (missing data message, 10 s timeouts, ICAO from OurAirports, rate-limit message): Tasks 5, 9, 10.
- Spec §8 testing (unit on synthetic frame, integration skipped without data, manual four questions): Tasks 3, 4, 5, 7, 8, 9, 10.
- Spec §9 four sample questions → tools: Task 9 Step 5 verifies each.
- Spec §10–11: recorded in DESIGN.md (Task 11); open points verified before this plan was written (2025 complete; `FMG` has the country fields; SDK schema generation OK).
