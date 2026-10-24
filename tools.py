"""The six deterministic tools the model may call.

Every function returns a JSON-serializable dict, never raises, and carries `meta` + `caveats` so the model
can cite data year/source and state limits. This file only computes: the descriptions Gemini sees live in
agent/tools.md (applied to the functions at the bottom) and every sentence attached to a result in
agent/caveats.md.
"""
from __future__ import annotations

import functools
import re

import pandas as pd

import agentfiles
import config
import live
import metrics

_c = agentfiles.caveat


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


def methodology(t: pd.DataFrame) -> dict:
    """The score explained, rendered from agent/methodology.md. The same text goes to the model and to the sidebar."""
    weights_table = "| component | weight |\n|---|---|\n" + "\n".join(f"| {k} | {v:.2f} |" for k, v in config.WEIGHTS.items())
    text = agentfiles.render(agentfiles.read("methodology.md"), universe_size=int(t.in_universe.sum()),
                             universe_min_passengers=config.UNIVERSE_MIN_PASSENGERS, data_year=config.YEARS[-1],
                             min_runway_ft=config.MIN_RUNWAY_FT, weights_table=weights_table)
    return {"text": text, "weights": config.WEIGHTS}


def _pct(x) -> float | None:
    return None if pd.isna(x) else round(float(x) * 100, 1)


def _caveats(r: pd.Series) -> list[str]:
    c = []
    if pd.isna(r["runways"]):
        c.append(_c("no_runways"))
    if pd.isna(r["growth_yoy"]):
        c.append(_c("no_prior_year", prior_year=config.YEARS[0]))
    if not r["in_universe"]:
        c.append(_c("below_universe", universe_min_passengers=config.UNIVERSE_MIN_PASSENGERS))
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


# The six tools. Their docstrings are assigned from agent/tools.md below.

def _metro_matches(query: str, metros: dict[str, list[str]]) -> list[str]:
    """Metro names whose full name, a whole word of it, or (for queries longer than 3 characters) any part of it matches."""
    q = query.strip().lower()
    out = []
    for name in metros:
        name_l = name.lower()
        if q == name_l or q in re.findall(r"[a-z]+", name_l) or (len(q) > 3 and q in name_l):
            out.append(name)
    return out


def search_airports(query: str) -> dict:
    t, d = _table()
    q = query.strip().lower()
    u = t[t.in_universe]
    hit = u[(u.index.str.lower() == q)
            | u["name"].fillna("").str.lower().str.contains(q, regex=False)
            | u["municipality"].fillna("").str.lower().str.contains(q, regex=False)]
    matches = [{"code": c, "name": r["name"], "city": r["municipality"], "state": r["state"]} for c, r in hit.head(10).iterrows()]
    metro_list = []
    for name in _metro_matches(query, d.get("metros", {})):
        codes = [c for c in d["metros"][name] if c in t.index]
        metro_list.append({"metro": name, "airports": [
            {"code": c, "name": t.loc[c, "name"], "city": t.loc[c, "municipality"], "state": t.loc[c, "state"],
             "in_universe": bool(t.loc[c, "in_universe"]), "primary": i == 0} for i, c in enumerate(codes)]})
    ambiguous = bool(metro_list) or len(matches) > 1
    hint = _c("search_ambiguous") if ambiguous else ("" if matches else _c("search_no_match"))
    return metrics.jsonable({"query": query, "matches": matches, "metros": metro_list, "meta": _meta(t), "hint": hint})


def rank_airports(region: str = "", states: list[str] | None = None, top_n: int = 10) -> dict:
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
        "methodology": methodology(t), "meta": _meta(t),
        "caveats": [_c("not_roi"), _c("weights_judgment")],
    })


def airport_profile(code: str) -> dict:
    t, d = _table()
    code = code.strip().upper()
    if code not in t.index:
        return {"error": f"{code} not found in T-100 data", "hint": "use search_airports to find the code"}
    r = t.loc[code]
    out = _row_summary(r, d["notes"])
    out["live"] = live_status(code)
    median = float(t[t.in_universe].growth_yoy.median())
    unmet = metrics.unmet_demand(r, d["notes"], out["live"]["faa"]["entries"], median)
    unmet["thresholds"] = {
        "full_flights": _c("unmet_full_flights", load_factor=config.UNMET["load_factor"]),
        "runway_constrained": _c("unmet_runway_constrained", pressure_pct=config.UNMET["pressure_pct"]),
        "growing": _c("unmet_growing", median_growth=median),
        "live_congestion": _c("unmet_live_congestion"),
        "structural_constraint": _c("unmet_structural"),
    }
    unmet["note"] = _c("unmet_proxy")
    out["unmet_demand"] = unmet
    out["methodology"] = methodology(t)
    out["meta"] = _meta(t)
    return metrics.jsonable(out)


def compare_airports(codes: list[str]) -> dict:
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
    return metrics.jsonable({"airports": profiles, "methodology": methodology(t), "meta": _meta(t),
                             "caveats": [_c("congestion_reading"), _c("live_snapshot")]})


def long_haul_share(code: str, threshold_miles: int = config.LONG_HAUL_MILES) -> dict:
    t, d = _table()
    code = code.strip().upper()
    if code not in t.index:
        return {"error": f"{code} not found in T-100 data", "hint": "use search_airports to find the code"}
    miles = int(threshold_miles)
    out = metrics.long_haul(d["od"], code, config.YEARS[-1], miles)
    out["definition"] = _c("long_haul_definition", threshold_miles=miles)
    out["curated_notes"] = d["notes"].get(code, [])
    out["meta"] = _meta(t)
    out["caveats"] = [_c("long_haul_threshold", threshold_miles=miles), _c("long_haul_by_departures")]
    return metrics.jsonable(out)


def live_status(code: str) -> dict:
    t, _ = _table()
    code = code.strip().upper()
    faa = live.faa_status()
    icao = t.icao.get(code) if code in t.index else None
    return metrics.jsonable({
        "airport": code,
        "faa": {"updated": faa.get("updated"), "entries": faa.get("entries", {}).get(code, []), "error": faa.get("error")},
        "opensky": live.opensky_departures(icao),
        "caveats": [_c("faa_snapshot")],
    })


TOOLS = [search_airports, rank_airports, airport_profile, compare_airports, long_haul_share, live_status]
agentfiles.apply_tool_docs(TOOLS, regions=", ".join(config.REGIONS))
