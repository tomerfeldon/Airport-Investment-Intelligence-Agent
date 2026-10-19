# Tool descriptions

One section per function in `tools.py`. The section body becomes the function's docstring, which is the
schema description Gemini sees; `{regions}` is rendered from `config.REGIONS`. A section without a function,
or a function without a section, fails at import.

## search_airports
Find airports in the ranking universe by IATA code, airport name or city. Use when unsure of a code.

Args:
    query: free text such as "Santa Ana", "Logan", "SNA"

## rank_airports
Rank US airports by Expansion Opportunity Score (0-100), optionally filtered to a region or states.

Args:
    region: {regions}; empty string for the whole US
    states: two-letter state codes such as ["MA", "CT"]; used only when region is empty
    top_n: number of airports to return (1-50)

## airport_profile
Full profile of one airport: metrics, score breakdown, unmet-demand signal, curated notes and live status.

Args:
    code: IATA code such as "SFO"

## compare_airports
Compare 2-5 airports side by side on every metric, score breakdown, unmet-demand signal and live status.

Args:
    codes: IATA codes such as ["LAX", "SNA"]

## long_haul_share
Share of an airport's departures that are long haul, for passenger service and all-cargo service separately.

Args:
    code: IATA code such as "ANC"
    threshold_miles: nonstop segment distance that counts as long haul (default 1500 statute miles)

## live_status
Current FAA delay/ground-stop/closure status for an airport and, if configured, yesterday's OpenSky departure count.

Args:
    code: IATA code such as "EWR"
