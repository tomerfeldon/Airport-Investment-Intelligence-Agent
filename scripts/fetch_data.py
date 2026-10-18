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
            & ap["type"].isin(["large_airport", "medium_airport", "small_airport"])]
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
