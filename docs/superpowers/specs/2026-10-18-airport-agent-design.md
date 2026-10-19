# Airport Investment Intelligence Agent - Design Spec

Date: 2026-10-18 · Status: draft for review · Scope: one-day take-home assignment

## 1. Goal and framing

An analyst at a US airport-modernization investment firm asks questions in plain English
("Which New England airports are strong candidates for terminal expansion?") and gets a
ranked, explained, number-backed answer with follow-up support.

Stance that drives every decision below:

- **Numbers come from deterministic code over public data.** The LLM never computes a metric.
- **The LLM does two jobs:** map a question to tool calls (with arguments), and narrate the
  tool results - including the caveats the tools return.
- **The score measures capacity-expansion *opportunity*, not ROI.** Public data has no CAPEX,
  land, or politics; the doc says so.

## 2. Scope

In scope
- Universe: US airports with ≥ 500,000 originating passengers (passenger service) in the latest
  data year - roughly the 110 largest. Threshold lives in `config.py`.
- Question types: rank/filter by region or states; compare 2–5 airports; single-airport profile;
  long-haul share; unmet-demand signal; live status overlay; conversational follow-ups.
- Chat UI (Streamlit). Voice input is an optional bonus (last step).
- Deliverables: source, `README.md` (run instructions, screenshots), `DESIGN.md`.

Out of scope (stated in DESIGN.md as future work)
- Cost/ROI modeling, gate/terminal-area data (no public structured source), forecasting,
  monthly seasonality, non-US airports, auth/DB/deployment.

## 3. Data sources

| Source | Gives | Access | Role |
|---|---|---|---|
| **BTS T-100 Segment (All Carriers)**, TranStats table `FMG` | per segment × month × carrier: `DEPARTURES_PERFORMED`, `SEATS`, `PASSENGERS`, `FREIGHT`, `DISTANCE`, `ORIGIN/DEST` (+ state, country), `AIRCRAFT_TYPE`, `CLASS`, `YEAR`, `MONTH` | `scripts/fetch_data.py` replays the TranStats download form: GET (session cookie + `__VIEWSTATE`/`__EVENTVALIDATION`) → POST field checkboxes + `cboGeography=All`, `cboYear`, `cboPeriod=All`, `btnDownload=Download` → zip → CSV. Verified working 2026-10-18 on the sibling table `FIM`. | Backbone: demand, load factor, departures, distance |
| **OurAirports** `airports.csv`, `runways.csv` (public domain) | IATA/ICAO codes, lat/lon, `iso_region` (e.g. `US-MA`), municipality; runway `length_ft`, `closed` | Direct CSV URLs on `davidmegginson.github.io/ourairports-data/`, fetched by the same script | Physical capacity proxy, region filter, ICAO for OpenSky |
| **FAA NAS Status** | Current ground delay programs, ground stops, arrival/departure delays, closures, with reason | `https://nasstatus.faa.gov/api/airport-status-information` (XML, no key). Verified 2026-10-18. | Live congestion overlay |
| **OpenSky Network** (optional) | Yesterday's departures per airport (ICAO), with estimated destination | `GET /api/flights/departure?airport=&begin=&end=`, OAuth2 client-credentials (free account); anonymous works with 400 credits/day. Verified 2026-10-18. | Live departure count and top destinations; "not configured" when env vars are absent |
| **Curated notes** `data/airport_notes.json` | ≤ 10 structural facts with a source URL each (e.g. SFO closely spaced parallel runways; SNA 5,701 ft runway + legal passenger cap + curfew; LGA/DCA perimeter & slot rules; ANC Asia–US cargo stop) | Hand-written at implementation time, every fact verified against its source | Honest injection of domain knowledge the data cannot see; rendered with the label "curated note" |

Data years: the latest two complete calendar years available in T-100 (expected 2024 and 2025;
`config.YEARS`). If 2025 is incomplete at implementation time, use 2023–2024.

Processed data is **committed** so a reviewer can run the app without touching BTS:
`data/t100_od_annual.csv.gz` (aggregated to year × origin × dest × class, ≈ 70k rows, < 1 MB),
`data/airports_us.csv`, `data/runways_us.csv`. Raw zips go to `data/raw/` (gitignored).

## 4. Metrics (per airport, latest data year unless noted)

Service classes: passenger service = `CLASS ∈ {F, L}`; all-cargo = `CLASS ∈ {G, P}`.
Rows with `DEPARTURES_PERFORMED = 0` are dropped.

| Metric | Definition | Service classes |
|---|---|---|
| `passengers`, `seats`, `departures` | sums over segments with `ORIGIN = airport` | passenger |
| `load_factor` | `passengers / seats` | passenger |
| `departures_all` | departures of every class - runways are consumed by cargo too | all |
| `runways` | OurAirports runways for the airport with `closed = 0` and `length_ft ≥ 5000` (`config.MIN_RUNWAY_FT`) | - |
| `runway_pressure` | `departures_all / 365 / runways` (departures per runway per day) | all |
| `growth_yoy` | `passengers_latest / passengers_prior − 1` | passenger |
| `avg_stage_mi` | `Σ(distance × departures) / Σ departures` | passenger |
| `long_haul_share(threshold)` | `Σ departures with distance ≥ threshold / Σ departures`, default 1,500 mi, reported for passenger and all-cargo separately, plus top-5 long-haul destinations by departures | both |
| `intl_share` | departures with `DEST_COUNTRY ≠ US / departures_all` | all |

Missing data: an airport with no runway match or no prior-year row gets `NaN` for that metric;
the score renormalizes the remaining weights and adds a caveat. Nothing is silently zero-filled.

## 5. Expansion Opportunity Score (0–100)

```
score = 100 × Σ wᵢ · pctᵢ      pctᵢ = percentile rank of metricᵢ within the universe (0–1)
```

| Component | Weight | Why |
|---|---|---|
| `runway_pressure` | 0.35 | Most direct public signal of a physical bottleneck |
| `passengers` | 0.25 | Market size - expansion must have someone to serve |
| `load_factor` | 0.25 | Full aircraft = demand airlines can't add seats for |
| `growth_yoy` | 0.15 | Investment is on the future, not the present |

Decisions
- **Percentile rank, not min-max:** robust to ATL/LAX outliers; "score 85" reads as "top 15%".
  Percentile ranking is invariant to monotonic transforms, so no log on passengers is needed.
- **Live signals are not in the score.** A ranking that changes with the weather is not a ranking.
  FAA/OpenSky appear as a separate "right now" overlay in every profile/comparison.
- **Weights are judgment, not fitted** - there is no public ground truth for "profitable
  renovation". They live in `config.WEIGHTS` and DESIGN.md says exactly this.

Every score is returned with a `breakdown`: one row per component with raw value, percentile,
weight, contribution - this is what the LLM uses to explain "why".

### Unmet-demand signal (proxy)

Flags, each with its threshold in config:
`full_flights` (LF ≥ 0.85) · `runway_constrained` (pressure percentile ≥ 0.80) ·
`growing` (growth above universe median) · `live_congestion` (FAA lists the airport now) ·
`structural_constraint` (curated note of type `constraint`).
Level: 0–1 flags → low, 2–3 → moderate, 4–5 → high. The tool result always carries the sentence:
"Proxy signal - passengers who chose another airport or didn't fly are not observable in public data."

## 6. Architecture

```
Streamlit chat (app.py)
   │  user text (+ optional transcribed audio)
   ▼
agent.py - Gemini, manual tool loop (≤ 6 iterations), returns text + tool trace
   │  function calls / function responses
   ▼
tools.py - 6 deterministic functions returning JSON-serializable dicts
   ├── metrics.py   pandas: load data/, build per-airport table, score, breakdown
   ├── live.py      FAA XML parser, OpenSky client (token cache, 10 s timeouts)
   └── config.py    weights, thresholds, regions, years, model name, universe threshold
scripts/fetch_data.py - offline: TranStats + OurAirports → data/*.csv(.gz)
tests/test_metrics.py
```

### Tools (exact signatures; docstrings become the schema Gemini sees)

1. `search_airports(query: str) -> list[dict]` - match IATA / name / city within the universe
   (used when the LLM is unsure of a code: "Santa Ana" → SNA).
2. `rank_airports(region: str = "", states: list[str] | None = None, top_n: int = 10) -> dict` -
   `region` ∈ `config.REGIONS` (`new_england` = MA CT RI NH VT ME, `mid_atlantic`, `southeast`,
   `midwest`, `texas`, `mountain_west`, `west_coast`, `pacific_northwest`, `alaska_hawaii`);
   `states` for anything else. Returns filter applied, universe size, rows with score,
   key metrics and breakdown.
3. `airport_profile(code: str) -> dict` - all metrics, breakdown, unmet-demand flags, curated
   note, live status.
4. `compare_airports(codes: list[str]) -> dict` - 2–5 airports side by side, same fields.
5. `long_haul_share(code: str, threshold_miles: int = 1500) -> dict` - passenger and all-cargo
   shares, top destinations, curated notes for the airport.
6. `live_status(code: str) -> dict` - FAA entries for the airport; OpenSky departures yesterday.

Every result carries `meta` (`data_year`, `prior_year`, `source`, `universe_size`) and
`caveats: list[str]`. Unknown code → `{"error": ..., "suggestions": [...]}`; the model asks the user.
An airport in T-100 but below the universe threshold gets metrics but `score = None` with a caveat.

### Agent loop (agent.py)

- `genai.Client()` with `GEMINI_API_KEY`; model `config.MODEL` (default `gemini-3.8-flash`,
  stable and free-tier per Google's pricing page on 2026-10-18; override via `GEMINI_MODEL`).
- `GenerateContentConfig(tools=[the 6 functions], system_instruction=SYSTEM_PROMPT,
  automatic_function_calling=AutomaticFunctionCallingConfig(disable=True), temperature=0.2)`.
  The SDK still generates the function schemas from type hints + docstrings; we run the loop
  ourselves so every call and result is captured for the UI and errors are returned to the
  model as `{"error": ...}` instead of crashing.
- `ask(history, text) -> (answer, trace, history)`: append user content; loop: generate; if
  `response.function_calls` → execute each, append model content and a `user` content built with
  `Part.from_function_response`; else return text. Cap 6 iterations.
- 429/503 → exponential backoff, 3 attempts, then a friendly message.
- System prompt rules: analyst assistant for airport-expansion investment; every number must
  come from a tool; cite data year and source; resolve ambiguous names with `search_airports`
  ("LA" → LAX, say so); answer structure = direct answer → ranking/table → reasoning from the
  breakdown → caveats and assumptions; keep conversation context for follow-ups; never
  present the score as profitability.

### UI (app.py)

- Sidebar: methodology summary with weights read from config, data vintage, live-source status
  chips (FAA reachable / OpenSky configured), four example-question buttons, clear chat.
- Chat: `st.chat_message` + `st.chat_input`; `st.session_state` holds Gemini history and display
  messages. Under each answer: expander "Data behind this answer" rendering the tool trace
  (arguments + result; tabular results as `st.dataframe`, others as JSON).
- Voice (bonus, if time remains): `st.audio_input` → audio bytes sent to Gemini with
  "transcribe verbatim" → text enters the chat like a typed message.

## 7. Error handling and uncertainty

- Missing `data/` files → app shows the fetch-script command instead of a stack trace.
- Live sources: 10 s timeout; any failure → caveat string in the result, never an exception.
- OpenSky needs ICAO (ANC = PANC, HNL = PHNL): taken from OurAirports `icao_code`, never derived
  as `"K" + IATA`. FAA uses FAA LIDs, equal to IATA for the universe; mismatches are reported as
  "no live status found", not as "no delays".
- Gemini rate limit → message asking to retry in a minute.

## 8. Testing

- Unit (`tests/test_metrics.py`, synthetic 3-airport frame): load factor, pressure, long-haul
  share, score ∈ [0, 100], weights sum to 1, NaN renormalization, region filter.
- Integration (skipped when `data/` is absent): BOS ranks first in New England; SFO load factor
  ∈ [0.6, 0.95]; ANC all-cargo long-haul share > passenger share; SNA `runways == 1`.
- Manual: the four assignment questions plus two follow-ups, screenshots into README.

## 9. How the four sample questions resolve

| Question | Tool call | Deterministic answer | LLM adds |
|---|---|---|---|
| New England terminal-expansion candidates | `rank_airports(region="new_england")` | ranked BOS, BDL, PVD, MHT, PWM, BTV with breakdowns | why each ranks where it does, caveat that score ≠ ROI |
| LA vs Santa Ana congestion | `compare_airports(["LAX","SNA"])` | pressure, LF, runways, growth, live status, SNA curated note (runway length, passenger cap) | interpretation: SNA constrained by law and runway, LAX by volume |
| Long-haul % out of Anchorage | `long_haul_share("ANC")` | passenger vs all-cargo shares, top destinations, threshold used | explains the cargo-hub effect and the threshold assumption |
| Unmet demand at SFO and why | `airport_profile("SFO")` | flags (LF, pressure, growth, live, parallel-runway note), level, breakdown | narrative "why", explicit proxy caveat |

## 10. Tradeoffs recorded for DESIGN.md

- Bulk T-100 replayed by script vs. a live REST API: depth (seats, distance) wins; BTS has no stable
  endpoint; liveness comes from FAA/OpenSky.
- Committed processed data vs. fetch at runtime: reviewer runs in one command; refresh is a script.
- Annual vs. monthly: seasonality lost, data stays tiny; acceptable for an investment ranking.
- Runway count as capacity proxy: the only public, structured one; blind spots (SFO parallels,
  SNA cap) covered by labeled curated notes rather than hidden heuristics.
- Manual tool loop vs. SDK automatic function calling: ~25 extra lines buy a visible trace and
  controlled error handling - the trace *is* the "explain your reasoning" feature.
- Gemini free tier vs. paid models: free, native function calling, ≤ 3 calls per question.

## 11. Verify during implementation

- 2025 complete in T-100 (otherwise `YEARS = [2023, 2024]`).
- `FMG` accepts `ORIGIN_COUNTRY` / `DEST_COUNTRY` field checkboxes (expected; else derive from
  `ORIGIN_STATE_ABR` being empty for foreign points).
- google-genai schema generation for `list[str]` and defaults; fall back to `str` with
  comma-separated codes if needed.
- Each curated note's fact and source.

## 12. Plan (≈ 7.5 h)

| # | Step | Est. |
|---|---|---|
| 0 | Repo, venv, `requirements.txt` (streamlit, pandas, requests, google-genai, python-dotenv, pytest), `.env.example`, `config.py` | 30 min |
| 1 | `scripts/fetch_data.py` → committed `data/` | 1 h |
| 2 | `metrics.py` + `tests/test_metrics.py` green | 1.5 h |
| 3 | `live.py` (FAA, OpenSky) | 45 min |
| 4 | `tools.py` + `agent.py`, CLI smoke test on the four questions | 1.5 h |
| 5 | `app.py` Streamlit chat with trace expander | 1 h |
| 6 | `DESIGN.md`, `README.md`, screenshots | 1 h |
| ★ | Voice input | 20 min, only if time remains |
