# Design — Airport Investment Intelligence Agent

## 1. Purpose and framing

We invest in US airport modernization. The agent helps an analyst find airports where added flight and
passenger capacity would be most valuable, and explains why with numbers the analyst can audit.

Three principles drive the design:

1. **Numbers come from deterministic code over public data.** The language model never calculates a metric.
2. **The model does two jobs:** translate a question into tool calls, and narrate the tool results — including
   the caveats the tools return.
3. **The score measures capacity-expansion *opportunity*, not profitability.** Public data carries no CAPEX,
   land, financing or politics, so the agent says so in every answer.

## 2. Scoring methodology

### 2.1 Universe
US airports with at least 500,000 originating passengers (passenger service) in the latest complete T-100
year (2025): 144 airports. This keeps the airports where a terminal or airfield program is plausible, including
the smaller New England hubs (PVD, PWM, BTV, HVN, MHT), while excluding general-aviation noise. Airports
below the threshold still get metrics, but no score — percentiles against the universe would be misleading.

### 2.2 Metrics (per airport, latest year)

| Metric | Definition | Why it matters |
|---|---|---|
| passengers, seats, departures | sums over segments departing the airport, passenger service (T-100 classes F + L) | demand volume |
| load factor | passengers / seats | full aircraft = demand airlines cannot add seats for |
| departures (all classes) | including all-cargo (G + P) — freighters consume runway slots too | runway demand |
| runways | OurAirports runways that are open and ≥ 5,000 ft | commercial-capable physical capacity |
| runway pressure | departures (all classes) / 365 / runways | departures per runway per day — the bottleneck proxy |
| growth | passengers latest / passengers prior − 1 (2025 vs 2024) | direction of travel |
| average stage length, international share, long-haul share | distance-weighted by departures | network character; answers "how long-haul is this airport?" |

### 2.3 Expansion Opportunity Score (0–100)

    score = 100 × Σ weightᵢ × percentile_rankᵢ        (percentiles within the universe)

| Component | Weight | Rationale |
|---|---|---|
| runway pressure | 0.35 | the most direct public signal of a physical bottleneck |
| passengers | 0.25 | market size — expansion needs someone to serve |
| load factor | 0.25 | full aircraft mean demand is being rationed |
| growth | 0.15 | investment is on the future, not the present |

Design decisions:
- **Percentile rank, not min–max.** Robust to ATL/LAX outliers, and "score 85" reads as "top 15%". Percentile
  ranking is invariant to monotonic transforms, so no log on passengers is needed.
- **Missing components drop out and the remaining weights renormalize**, with a caveat in the result, instead of
  silently scoring zero.
- **Live signals are not in the score.** A ranking that changes with the weather is not a ranking. FAA status and
  OpenSky counts are shown next to the score as a "right now" overlay.
- **Weights are analyst judgment, not fitted.** There is no public ground truth for "profitable renovation". They
  live in `config.py`, and every result returns a breakdown (component, percentile, weight, contribution) so a
  reader can disagree with a weight and still use the numbers.

### 2.4 Unmet-demand signal (a proxy, labeled as such)
Five flags with thresholds in `config.py`: full flights (load factor ≥ 85%), runway-constrained (pressure
percentile ≥ 80%), growing faster than the universe median, live FAA congestion, structural constraint (curated
note). 0–1 flags = low, 2–3 = moderate, 4–5 = high. Every result repeats: passengers who chose another airport
or did not fly are not observable in public data.

### 2.5 Long-haul share
Share of departures on nonstop segments of at least 1,500 statute miles (configurable per question), reported
separately for passenger and all-cargo service — at Anchorage the two tell opposite stories.

### 2.6 Worked example — New England, generated 2026-10-18 from 2025 data

| Airport | Score | Passengers | Load factor | Runways | Dep./runway/day | Growth YoY |
|---|---|---|---|---|---|---|
| BOS | 76.7 | 21,143,295 | 81.6% | 5 | 105.1 | −0.8% |
| BDL | 58.0 | 3,289,186 | 80.0% | 2 | 43.3 | −0.3% |
| PVD | 52.9 | 2,122,707 | 77.8% | 2 | 30.4 | +6.6% |
| PWM | 52.0 | 1,287,476 | 82.4% | 2 | 20.3 | +5.3% |
| BTV | 50.0 | 709,116 | 81.3% | 1 | 27.3 | +5.7% |
| HVN | 31.7 | 737,818 | 75.3% | 1 | 16.7 | +25.2% |
| MHT | 28.4 | 686,314 | 76.0% | 2 | 14.5 | +8.2% |

Reading it: BOS leads on volume and runway pressure; BDL and PVD are the second tier; the growth component is
what lifts HVN (New Haven) into view despite its size. Nationally the top five are ORD 87.5, SFO 86.5, ATL 85.7,
SEA 84.4 and DEN 82.5 — runway pressure and load factor, not raw size, separate them.

## 3. Data sources and their limits

| Source | What we use | How | Limits |
|---|---|---|---|
| BTS T-100 Segment (All Carriers) | per-segment departures, seats, passengers, distance, service class, 2024–2025 | `scripts/fetch_data.py` replays the TranStats download form (no stable URL exists); the annual aggregate (93k rows, 1.1 MB) is committed so reviewers need no download | 3–6 month publication lag; annual aggregation hides seasonality |
| OurAirports | runway length/status, coordinates, ICAO codes | public-domain CSV | runway count ignores spacing, taxiways, gates — see curated notes |
| FAA NAS Status | current ground delays, ground stops, closures | public XML, no key | snapshot only, no history |
| OpenSky Network (optional) | yesterday's departures per airport | REST + OAuth2, free account | volunteer-receiver coverage; counts are lower bounds |
| Curated notes | four verified structural facts (SNA passenger cap, SFO runway spacing, DCA slots/perimeter, ANC cargo stop) | hand-written JSON with source URLs, shown as "curated note" | small by design; a reviewer can see exactly what human knowledge was injected |

## 4. Where AI is used — and where it is deliberately not

**Used:** Gemini (`gemini-3.8-flash`, free tier, via `google-genai`) maps the question to one of six tools and
their arguments, narrates the result, keeps conversational context for follow-ups, and (bonus) transcribes
voice input.

**Not used:** every metric, percentile, score, flag and ranking is computed in `metrics.py` and `tools.py`;
`pytest` covers them with a synthetic dataset where the expected numbers are worked out by hand, plus
plausibility checks on the real data.

**Guardrails:** automatic function calling is disabled and the loop is ours, so the UI shows every tool call and
result under each answer ("Data behind this answer"); tool exceptions go back to the model as data; the system
prompt forbids numbers that did not come from a tool and requires an "Assumptions & caveats" section;
temperature 0.2.

## 5. Key tradeoffs

- **Replayed bulk download vs. a live API for traffic data.** Depth (seats, distance, class) was worth more than
  liveness; BTS has no REST endpoint; liveness comes from FAA/OpenSky instead.
- **Committed processed data vs. fetching at run time.** One command runs the app; refresh is a script.
- **Annual vs. monthly.** Seasonality is lost; the data stays under 2 MB and the ranking is stable.
- **Runway count as the capacity proxy.** The only public, structured one. Its blind spots (SFO's 750 ft runway
  spacing, SNA's legal cap) are covered by labeled curated notes rather than hidden heuristics.
- **Manual tool loop vs. SDK automatic function calling.** About 25 extra lines buy a visible trace and controlled
  error handling — the trace is the "explain your reasoning" feature.
- **Free Gemini tier.** No cost, native function calling; a question costs at most three model calls.

## 6. How assumptions, uncertainty and scope reach the user

Every tool result carries `meta` (data year, source, universe size) and `caveats`; the prompt makes the model
repeat them. Live sources degrade to an explicit "unavailable"/"not configured" rather than a silent zero. Airports
below the universe threshold get metrics but `score: null` and a caveat. Curated notes are labeled with their
source. The sidebar states the formula, the weights and what the score does not measure.

## 7. Limitations and next steps

Gate and terminal-area data (FAA ADIP) would turn "terminal expansion" from inference into measurement;
FAA ASPM would add delay history; monthly data would expose seasonal peaks; a cost layer (construction index,
land) would move the score toward ROI; a weight-sensitivity view in the UI would let analysts stress-test the
ranking; an evaluation set of analyst questions with expected tool calls would guard the prompt.
