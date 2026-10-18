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
