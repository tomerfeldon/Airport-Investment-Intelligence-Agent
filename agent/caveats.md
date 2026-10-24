# Caveats and standard sentences

Every sentence the tools attach to a result. `tools.py` and `live.py` read them by section name; placeholders
in braces are rendered from `config` or from the call's arguments.

## not_roi
Score measures capacity-expansion opportunity from public traffic and runway data; it is not an ROI estimate.

## weights_judgment
Weights are analyst judgment, not fitted to outcomes.

## congestion_reading
Higher departures per runway per day = more congested relative to physical capacity.

## live_snapshot
Live status is a snapshot at query time and is not part of the score.

## faa_snapshot
FAA status is a snapshot at query time, not history; an empty list means no current FAA advisory.

## opensky_coverage
OpenSky coverage depends on volunteer receivers; counts are lower bounds.

## long_haul_threshold
The {threshold_miles:,}-mile threshold is an assumption (1,500 mi is roughly a 3.5-hour flight). Ask for another threshold if needed.

## long_haul_by_departures
Shares are by departures performed, not by seats or passengers.

## long_haul_definition
long haul = nonstop segment distance >= {threshold_miles} statute miles (BTS great-circle); shares are by departures performed

## search_no_match
no match in the universe; the airport may be too small or spelled differently

## search_ambiguous
Several airports match this place. Show the user the list (code, name, city, which one is the primary airport) and ask which airport to use, or whether to compare all of them. Do not call any other tool until the user answers.

## no_runways
No runway data matched in OurAirports; runway pressure excluded and weights renormalized.

## no_prior_year
No {prior_year} data; growth excluded and weights renormalized.

## below_universe
Below the universe threshold ({universe_min_passengers:,} passengers); no score or percentiles.

## unmet_proxy
Proxy signal - passengers who chose another airport or didn't fly are not observable in public data.

## unmet_full_flights
load factor >= {load_factor:.0%}

## unmet_runway_constrained
runway-pressure percentile >= {pressure_pct:.0%}

## unmet_growing
passenger growth above the universe median ({median_growth:+.1%})

## unmet_live_congestion
FAA currently lists a delay, ground stop or closure

## unmet_structural
curated note of type 'constraint'
