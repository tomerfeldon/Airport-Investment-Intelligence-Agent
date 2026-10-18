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
