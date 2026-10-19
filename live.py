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

import agentfiles

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
            "caveat": agentfiles.caveat("opensky_coverage")}
