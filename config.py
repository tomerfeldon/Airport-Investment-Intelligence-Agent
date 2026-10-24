"""Every tunable knob of the agent. DESIGN.md explains each choice; nothing else lives here."""
import os

# Free-tier quotas are per model and per day (gemini-3.8-flash: 5 requests/minute, 20/day on 2026-10-19),
# so the agent walks this list when a model answers 429. GEMINI_MODEL, if set, goes first.
# gemini-2.5-flash was the last fallback until 2026-10-24, when it started returning 404 for new accounts.
MODELS = [m for m in dict.fromkeys([os.environ.get("GEMINI_MODEL", ""), "gemini-3.8-flash",
                                     "gemini-3.5-flash", "gemini-3.5-flash-lite"]) if m]

DATA_DIR = "data"
YEARS = [2024, 2025]                      # [prior, latest]; both must be complete calendar years in T-100

UNIVERSE_MIN_PASSENGERS = 500_000         # originating passengers (passenger service) in the latest year
MIN_RUNWAY_FT = 5000                      # shorter runways do not add commercial capacity
LONG_HAUL_MILES = 1500                    # default threshold for "long haul" segments

PASSENGER_CLASSES = {"F", "L"}            # T-100 CLASS: scheduled (F) and non-scheduled (L) passenger service
CARGO_CLASSES = {"G", "P"}                # scheduled (G) and non-scheduled (P) all-cargo service

# Expansion Opportunity Score = 100 * sum(weight * percentile rank within the universe). Must sum to 1.0.
WEIGHTS = {
    "runway_pressure": 0.35,              # departures per runway per day - the physical bottleneck
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
