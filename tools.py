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
