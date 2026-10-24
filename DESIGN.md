# Design - Airport Investment Intelligence Agent

## 1. Purpose and framing

We invest in US airport modernization. The agent helps an analyst find airports where added flight and
passenger capacity would be most valuable, and explains why with numbers the analyst can audit. Three principles
drive the design: **numbers come from deterministic code over public data** (the language model never calculates
a metric); **the model does two jobs**, translating a question into tool calls and narrating the results with the
caveats the tools return; **the score measures capacity-expansion opportunity, not profitability** (public data
carries no CAPEX, land, financing or politics, so every answer says so).

### 1.1 Architecture at a glance

    Analyst ---> Streamlit chat (app.py) ---> agent.py: Gemini tool loop <---> Gemini 3.8-flash (fallback chain)
                      ^                              |   picks a tool, narrates the result
                      |                              v
                      |                     tools.py: 6 read-only tools -> JSON + meta + caveats
                      |                       |                               |
                      |                  metrics.py                        live.py
                      |           score, flags, long-haul              FAA NAS status (60 s cache)
                      |           on committed extracts                OpenSky (optional, OAuth2)
                      |           (BTS T-100, OurAirports)
                      +------ every tool call and result is shown under the answer ("Data behind this answer")

Public data is frozen at build time (`scripts/fetch_data.py`), the live overlay is fetched at question time, and
the model never touches a number. The agent's definition (system prompt, tool descriptions, methodology text,
caveats, example questions, curated notes) is Markdown under `agent/` and `data/`, loaded at runtime by
`agentfiles.py`; Python only computes and executes.

## 2. Scoring methodology

### 2.1 Universe
US airports with at least 500,000 originating passengers (passenger service) in the latest complete T-100 year
(2025): 144 airports, roughly the FAA small-hub threshold. It keeps the smaller New England hubs (PVD, PWM, BTV,
HVN, MHT) and excludes general-aviation noise. Airports below the threshold get metrics but no score, because
percentiles against the universe would mislead.

### 2.2 Metrics (per airport, latest year)

| Metric | Definition | Why it matters |
|---|---|---|
| passengers, seats, departures | sums over segments departing the airport, passenger service (T-100 classes F + L) | demand volume |
| load factor | passengers / seats | full aircraft = demand airlines cannot add seats for |
| departures (all classes) | including all-cargo (G + P): freighters consume runway slots too | runway demand |
| runways | OurAirports runways that are open and >= 5,000 ft | commercial-capable physical capacity |
| runway pressure | departures (all classes) / 365 / runways | departures per runway per day: the bottleneck proxy |
| growth | passengers latest / passengers prior - 1 (2025 vs 2024) | direction of travel |
| stage length, international share, long-haul share | distance-weighted by departures | network character |

### 2.3 Expansion Opportunity Score (0-100)

    score = 100 × Σ weightᵢ × percentile_rankᵢ        (percentiles within the universe)

| Component | Weight | Rationale |
|---|---|---|
| runway pressure | 0.35 | the most direct public signal of a physical bottleneck |
| passengers | 0.25 | market size: expansion needs someone to serve |
| load factor | 0.25 | full aircraft mean demand is being rationed |
| growth | 0.15 | investment is on the future, not the present |

Design decisions: **percentile rank, not min-max** (robust to ATL/LAX outliers, "85" reads as "top 15%", no log
transform needed); **missing components drop out and the remaining weights renormalize**, with a caveat, instead of
silently scoring zero; **live signals are not in the score** (a ranking that changes with the weather is not a
ranking); **weights are analyst judgment, not fitted** (there is no public ground truth for "profitable renovation";
they live in `config.py` and every result returns the breakdown, so a reader can disagree with a weight and still
use the numbers).

### 2.4 Unmet-demand signal (a proxy, labeled as such)
Five flags with thresholds in `config.py`: load factor >= 85%, runway-pressure percentile >= 80%, growth above the
universe median, live FAA congestion, and a curated structural constraint. 0-1 flags = low, 2-3 = moderate,
4-5 = high. Every result repeats that passengers who chose another airport or did not fly are not observable.

### 2.5 Long-haul share
Share of departures on nonstop segments of at least 1,500 statute miles (configurable per question), reported
separately for passenger and all-cargo service: at Anchorage the two tell opposite stories.

### 2.6 Worked example: New England, generated 2026-10-18 from 2025 data

| Airport | Score | Passengers | Load factor | Runways | Dep./runway/day | Growth YoY |
|---|---|---|---|---|---|---|
| BOS | 76.7 | 21,143,295 | 81.6% | 5 | 105.1 | -0.8% |
| BDL | 58.0 | 3,289,186 | 80.0% | 2 | 43.3 | -0.3% |
| PVD | 52.9 | 2,122,707 | 77.8% | 2 | 30.4 | +6.6% |
| PWM | 52.0 | 1,287,476 | 82.4% | 2 | 20.3 | +5.3% |
| BTV | 50.0 | 709,116 | 81.3% | 1 | 27.3 | +5.7% |
| HVN | 31.7 | 737,818 | 75.3% | 1 | 16.7 | +25.2% |
| MHT | 28.4 | 686,314 | 76.0% | 2 | 14.5 | +8.2% |

BOS leads on volume and runway pressure; BDL and PVD are the second tier; the growth component lifts HVN into
view despite its size. Nationally the top five are ORD 87.5, SFO 86.5, ATL 85.7, SEA 84.4 and DEN 82.5: runway
pressure and load factor, not raw size, separate them.

## 3. Data sources and their limits

| Source | What we use | How | Limits |
|---|---|---|---|
| BTS T-100 Segment (All Carriers) | departures, seats, passengers, distance and service class per segment, 2024-2025 | no stable URL exists, so `scripts/fetch_data.py` replays the TranStats download form; the annual aggregate (93k rows, 1.1 MB) is committed | 3-6 month publication lag; annual data hides seasonality |
| OurAirports | runway length and status, coordinates, ICAO codes | public-domain CSV, same script | runway count ignores spacing, taxiways and gates |
| FAA NAS Status | current ground delays, ground stops, closures | public XML, no key, 60 s cache | snapshot only, no history |
| OpenSky Network (optional) | yesterday's departures per airport | REST + OAuth2, free account | volunteer coverage, counts are lower bounds (SFO: 463 vs 521 per day in BTS) |
| Curated notes | four verified structural facts (SNA passenger cap, SFO runway spacing, DCA slots and perimeter, ANC cargo stop) | `data/airport_notes.md`, a source URL per note, shown as "curated note" | small by design, so the injected human knowledge stays visible |

## 4. Where AI is used, and where it deliberately is not

**Used:** Gemini (`gemini-3.8-flash`, free tier, via `google-genai`) maps the question to one of six tools and
their arguments, narrates the result in the user's language (a Hebrew question gets a Hebrew answer), keeps
conversational context for follow-ups, and transcribes voice input (bonus). **Not used:** every metric, percentile,
score, flag and ranking is computed in `metrics.py` and `tools.py`, covered by 49 tests: a synthetic dataset with
hand-computed expectations, plausibility checks on the real data, and a faked model for the loop and the UI.
**Guardrails:** automatic function calling is disabled and the loop is ours, so every tool call and result is shown
under the answer; tool exceptions go back to the model as data; the prompt forbids numbers that did not come from a
tool and requires an "Assumptions & caveats" section; temperature 0.2. **Defined in Markdown, executed in Python:**
the system prompt, the tool descriptions Gemini sees, the methodology text, every caveat and the curated facts are
Markdown files loaded at runtime, so an analyst can change the agent's voice or knowledge without a developer, and a
tool description without a function (or the reverse) fails at import instead of drifting silently.

## 5. Key tradeoffs

- **Replayed bulk download vs a live API for traffic data:** depth (seats, distance, class) was worth more than liveness; liveness comes from FAA and OpenSky instead.
- **Committed processed data vs fetching at run time:** one command runs the app; refresh is a script.
- **Annual vs monthly:** seasonality is lost; the data stays under 2 MB and the ranking is stable.
- **Runway count as the capacity proxy:** the only public, structured one; its blind spots (SFO's 750 ft runway spacing, SNA's legal cap) are covered by labeled curated notes rather than hidden heuristics.
- **Manual tool loop vs SDK automatic function calling:** about 25 extra lines buy a visible trace and controlled error handling; the trace is the "explain your reasoning" feature.
- **Free Gemini tier:** no cost and native function calling, but small per-model quotas (5 requests per minute, 20 per day on 2026-10-19), so the loop falls back through lighter models and shows which one answered; production needs billing.
- **One model provider, by choice:** only `agent.py` talks to Gemini and the tools are plain functions, so swapping providers is a small, contained change.

## 6. How assumptions, uncertainty and scope reach the user

Every tool result carries `meta` (data year, source, universe size) and `caveats`, and the prompt makes the model
repeat them. Live sources degrade to an explicit "unavailable" rather than a silent zero. Airports below the
threshold get metrics but `score: null`. Curated notes are labeled with their source. The sidebar states the
formula, the weights and what the score does not measure. A city or metro name with several airports (Los
Angeles, Chicago, New York, Washington, the Bay Area; listed in `data/metros.md`) is never resolved silently: the
agent lists the airports with the primary one marked and asks which to use, or compares all of them on request.

## 7. Limitations and next steps

Runway pressure and passengers are strongly correlated (Spearman 0.89 across the universe), so 60% of the weight
is effectively airport size; FAA hub tiers as peer groups are the next methodology step. Next data steps: FAA ADIP
gate data to measure terminal capacity directly, BTS On-Time Performance for delays, monthly data for seasonal
peaks, a cost layer toward ROI, and an automated evaluation set of analyst questions with expected tool calls.
