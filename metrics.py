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
