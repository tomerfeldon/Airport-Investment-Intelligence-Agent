# Sample answers - the four assignment questions

Generated 2026-10-19 with `gemini-3.8-flash` through `python agent.py "<question>"`. The `[tool]` lines are the
deterministic calls the model made; everything numeric in the answers comes from them. FAA "live status" lines
reflect the moment of the query and will differ when you run it.

---

## 1. Which airports in New England are strong candidates for terminal expansion?

```
[tool] rank_airports({'region': 'new_england'})
[tool] airport_profile({'code': 'BOS'})
[tool] airport_profile({'code': 'BDL'})
```

### Direct Answer
Boston Logan International Airport (BOS) is the primary candidate for terminal and capacity expansion in New England, with an Expansion Opportunity Score of 76.7 (ranked 16th nationally). Bradley International Airport (BDL) ranks second in the region with a score of 58.0 (ranked 43rd nationally).

### Key Metrics for New England Airports

| Airport | Code | City, State | Score | National Rank | 2025 Passengers | Runway Pressure (dep/rwy/day) | Load Factor (%) | YoY Growth (%) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Boston Logan International | BOS | Boston, MA | 76.7 | 16 | 21,143,295 | 105.1 | 81.6% | -0.8% |
| Bradley International | BDL | Hartford, CT | 58.0 | 43 | 3,289,186 | 43.3 | 80% | -0.3% |
| Rhode Island T. F. Green | PVD | Providence/Warwick, RI | 52.9 | 54 | 2,122,707 | 30.4 | 77.8% | 6.6% |
| Portland International Jetport | PWM | Portland, ME | 52.0 | 58 | 1,287,476 | 20.3 | 82.4% | 5.3% |
| Patrick Leahy Burlington International | BTV | Burlington, VT | 50.0 | 65 | 709,116 | 27.3 | 81.3% | 5.7% |
| Tweed New Haven | HVN | New Haven, CT | 31.7 | 123 | 737,818 | 16.7 | 75.3% | 25.2% |
| Manchester-Boston Regional | MHT | Manchester, NH | 28.4 | 127 | 686,314 | 14.5 | 76% | 8.2% |

### Reasoning

* **Boston Logan International (BOS):**
  * **Runway Pressure:** 105.1 departures per runway per day places BOS in the 82.9th percentile (0.35 weight, contributing 29.0 points), triggering the unmet-demand signal for runway constraints (threshold >= 80%).
  * **Passenger Scale:** 21,143,295 originating passengers puts BOS in the 89.6th percentile (0.25 weight, contributing 22.4 points).
  * **Load Factor:** At 81.6%, BOS ranks in the 81.2th percentile (0.25 weight, contributing 20.3 points).
  * **Growth:** YoY growth was -0.8% (33.3rd percentile, 0.15 weight, contributing 5.0 points).
  * *Note on Live Status:* Live status indicates FAA arrival delays (16-30 minutes due to runway construction); live FAA status is a real-time snapshot and is never part of the score.
* **Bradley International (BDL):**
  * Serves as New England's secondary hub, with passenger volume (3,289,186 passengers, 62.5th percentile, contributing 15.6 points) and runway utilization (43.3 departures/runway/day, 56.1st percentile, contributing 19.6 points) placing it near the national median.
* **Secondary Growth Candidates:**
  * **PVD** and **PWM** exhibit moderate overall scores (52.9 and 52.0), but higher year-over-year traffic gains (6.6% and 5.3% YoY growth, respectively). In particular, PWM operates at an 82.4% load factor (87.5th percentile).

### Assumptions & Caveats

* **Data Year & Source:** Data reflects calendar year 2025 (prior year 2024), sourced from the BTS T-100 Segment (All Carriers) via TranStats, and OurAirports runway data.
* **Universe:** 144 US airports with >= 500,000 originating passengers in 2025.
* **Opportunity vs. Profitability:** The Expansion Opportunity Score measures capacity-expansion opportunity from public traffic and runway utilization; it is not an estimate of profitability or return on investment (ROI).
* **Methodology Caveats:**
  * Weights are based on analyst judgment, not fitted to commercial outcomes.
  * Runways are counted only when open and >= 5,000 feet.

---

## 2. Compare LA and Santa Ana airport congestion levels.

```
[tool] compare_airports({'codes': ['LAX', 'SNA']})
```

For this comparison, Los Angeles is resolved to its primary commercial airport, Los Angeles International Airport (LAX), and Santa Ana is resolved to John Wayne Orange County International Airport (SNA).

LAX exhibits higher overall operational congestion and runway pressure than SNA, ranking 10th nationally with an Expansion Opportunity Score of 80.4 compared to SNA's rank of 19th with a score of 74.0. However, while LAX faces high flight intensity on 4 runways, SNA experiences severe physical and regulatory constraints operating as a single-runway commercial airport.

### Key Metrics Comparison

| Metric | Los Angeles (LAX) | Santa Ana (SNA) |
|---|---|---|
| **Expansion Opportunity Score** | 80.4 (Rank 10) | 74.0 (Rank 19) |
| **Counted Commercial Runways** | 4 | 1 |
| **Departures / Runway / Day** | 187.6 | 140.4 |
| **Annual Passengers** | 36,778,508 | 5,532,646 |
| **Passenger Load Factor** | 81.6% | 79.7% |
| **Passenger Growth (YoY)** | -3.8% | 2.7% |
| **Unmet-Demand Level** | moderate (2 flags) | moderate (3 flags) |

### Score Breakdown & Congestion Reasoning

* **Runway Pressure (35% weight):** LAX registers 187.6 departures per runway per day (95.7th percentile, contributing 33.5 points), compared to SNA's 140.4 departures per runway per day (89.3rd percentile, contributing 31.2 points). Both meet the threshold for the runway-constrained unmet demand flag (percentile >= 80%).
* **Passenger Volume (25% weight):** LAX operates at massive hub scale with 36,778,508 passengers (97.2nd percentile, contributing 24.3 points) versus SNA's 5,532,646 passengers (72.2nd percentile, contributing 18.1 points).
* **Load Factor (25% weight):** LAX planes are fuller on average at 81.6% (79.9th percentile, contributing 20.0 points) than SNA's 79.7% (60.4th percentile, contributing 15.1 points). Neither meets the full flights threshold of >= 85%.
* **YoY Growth (15% weight):** SNA is expanding faster at 2.7% growth (63.9th percentile, contributing 9.6 points), triggering the unmet-demand growing flag (above the universe median of +1.3%), whereas LAX contracted by -3.8% (17.4th percentile, contributing 2.6 points).
* **Structural & Regulatory Constraints:** A curated note for SNA highlights that commercial service relies on a single runway (20R/2L, ~5,700 ft) governed by the John Wayne Airport Settlement Agreement, which caps annual passenger totals (11.8M through 2025, 12.2M conditional for 2026-2030), restricts daily departures, and imposes a nighttime curfew (10 p.m.-7 a.m. through 2035). As noted, capacity at SNA is legal before it is physical.
* **Live Status:** At query time, LAX had an active FAA closure advisory concerning non-scheduled transient GA aircraft (triggering its live congestion flag), while SNA had no active FAA advisories. This live status is a snapshot and is not part of the score.

### Assumptions & Caveats

* **Data year and source:** 2025 data (comparing against 2024 prior year) sourced from BTS T-100 Segment (All Carriers) via TranStats, and OurAirports for runway counts.
* **Runway pressure metric:** Higher departures per runway per day indicates more congestion relative to physical capacity. Only open runways >= 5,000 ft are counted.
* **Live status snapshot:** FAA delay/closure notices are real-time query snapshots, not historical operational records, and do not factor into the Expansion Opportunity Score.
* **Unmet demand proxy:** Unmet demand flags are proxy signals; passengers diverted to neighboring airports or choosing not to travel are unobservable in public aviation data.
* **Scope of score:** The Expansion Opportunity Score evaluates capacity-expansion opportunity, not profitability or financial ROI.

---

## 3. What is the percentage of long haul flights out of Anchorage airport?

```
[tool] long_haul_share({'code': 'ANC'})
```

For Anchorage, the primary commercial airport is Ted Stevens Anchorage International Airport (ANC). At ANC, long-haul flights (>= 1,500 statute miles) account for **17.7%** of passenger departures and **73.2%** of all-cargo departures.

### Long-Haul Departure Summary (ANC)

| Service Type | Total Departures | Long-Haul Departures | Long-Haul Share | Top Long-Haul Destinations |
| :--- | :--- | :--- | :--- | :--- |
| **Passenger Service** | 38,168 | 6,746 | 17.7% | PDX (1,459), MSP (853), ORD (781), DEN (609), HNL (384) |
| **All-Cargo Service** | 49,820 | 36,478 | 73.2% | ORD (7,629), SDF (2,815), JFK (2,577), HKG (2,529), MIA (2,372) |

### Operational Context & Reasoning

* **Cargo Hub Dominance**: Long-haul cargo operations heavily outweigh passenger long-haul operations at ANC, both in volume (36,478 vs. 6,746 departures) and departure share (73.2% vs. 17.7%).
* **Technical Transit Stops**: A curated note (source: Alaska's News Source, verified 2026-10-18) highlights that ANC was the world's #3 cargo airport in ACI's 2025 ranking (#4 in 2024), largely because roughly 80% of trans-Pacific freighters make a technical stop here to refuel and change crews. Most all-cargo departures represent long-haul transit operations rather than local origin/destination demand.
* **Passenger Flight Profile**: The lower passenger long-haul share (17.7%) reflects ANC's vital role in regional intra-Alaska transport alongside trunk routes connecting to major Lower 48 hubs (e.g., PDX, MSP, ORD, and DEN) and Hawaii (HNL).

### Assumptions & Caveats

* **Data Year & Source**: 2025 data from the BTS T-100 Segment (All Carriers) via TranStats and OurAirports runways (universe size: 144 airports).
* **Threshold Definition**: Long haul is defined as a nonstop segment distance >= 1,500 statute miles (BTS great-circle distance). The 1,500-mile threshold is an assumption representing roughly a 3.5-hour flight.
* **Measurement Basis**: Shares are by departures performed, not by available seats, cargo tonnage, or passenger counts.
* **Investment Scope**: Airport metrics and scores evaluate capacity-expansion opportunity, not airport profitability.

---

## 4. What is the unmet flight demand in SFO airport and why?

```
[tool] airport_profile({'code': 'SFO'})
```

### Direct Answer
San Francisco International Airport (SFO) exhibits a **moderate** unmet-demand signal (3 of 5 unmet-demand flags active) and holds an Expansion Opportunity Score of **86.5** (ranked #2 nationally). The unmet demand is driven by high runway pressure, above-median passenger growth, and severe structural runway layout constraints that restrict arrival throughput.

### Key Metrics & Score Breakdown

| Metric / Component | Raw Value | Universe Percentile | Weight | Score Contribution |
| :--- | :--- | :--- | :--- | :--- |
| **Runway Pressure** | 130.2 departures/runway/day | 0.871 | 0.35 | 30.5 |
| **Passengers** | 26,488,386 | 0.938 | 0.25 | 23.4 |
| **Load Factor** | 82.3% | 0.868 | 0.25 | 21.7 |
| **YoY Passenger Growth** | 4.7% | 0.722 | 0.15 | 10.8 |
| **Total Score** | - | - | - | **86.5** |

#### Unmet-Demand Indicators

| Flag | Status | Threshold / Definition |
| :--- | :--- | :--- |
| **Runway Constrained** | **True** | Runway-pressure percentile >= 80% (SFO is at the 87.1st percentile) |
| **Structural Constraint** | **True** | Curated note of type `constraint` exists |
| **Growing** | **True** | Passenger growth above universe median of +1.3% (SFO is at 4.7%) |
| **Full Flights** | **False** | Load factor >= 85% (SFO is at 82.3%) |
| **Live Congestion** | **False** | FAA currently lists a delay, ground stop, or closure (none active) |

### Reasoning

1. **Airfield Runway Pressure**: SFO handles 190,110 departures across 4 qualified runways, resulting in 130.2 departures per runway per day. This places SFO at the 87.1st percentile nationally and provides the single largest component contribution (30.5 points) to its expansion opportunity score.
2. **Structural Layout Bottlenecks**: Per a curated note (Source: OPSGROUP), SFO's airfield consists of two pairs of parallel runways separated by only 750 feet (independent parallel approaches require 4,300 feet). In 2025, the FAA banned side-by-side parallel visual approaches, cutting good-weather arrival capacity from roughly 54 to approximately 36 aircraft per hour. Because low visibility already required single-stream arrivals, the airport's four runways effectively operate like two for arrivals, creating a hard physical ceiling on flight capacity.
3. **Sustained Passenger Growth**: SFO logged 26,488,386 originating passengers (93.8th percentile) and grew 4.7% year-over-year, outpacing the national universe median of +1.3% and sustaining pressure on limited airfield slots.
4. **Load Factors**: Flights operate at an average load factor of 82.3% (86.8th percentile), reflecting high flight utilization, though slightly below the specific 85.0% threshold required to trigger the "full flights" flag.
5. **Live Status**: There are no active FAA ground stops, delays, or closures at query time. Note that live status is a snapshot and is never part of the score.

### Assumptions & Caveats

* **Data Year & Source**: Data is for 2025 (prior year 2024), sourced from BTS T-100 Segment (All Carriers) via TranStats, with runway configurations from OurAirports (universe of 144 US airports with >= 500,000 originating passengers).
* **Capacity Focus**: The Expansion Opportunity Score measures capacity-expansion opportunity, not profitability or investment return (ROI).
* **Unmet-Demand Proxy**: Unmet demand is an indirect proxy; travelers who selected alternative regional airports or chose not to fly cannot be directly observed in public BTS data.
* **Live Status Snapshot**: FAA status reflects a real-time snapshot at query time, not operational history, and is not factored into the score.

## Update 2026-10-24: city names with several airports

Since 2026-10-24 the agent never picks an airport for a city or metro name. `search_airports` returns the
metro's airports from `data/metros.md` and the agent lists them and asks. Two live conversations on
`gemini-3.8-flash` (each turn took 150-280 s on that day because the API itself was slow; the tool calls are
instant):

**"Compare Los Angeles and Chicago airport congestion levels."**
Tools: `search_airports(query='Los Angeles')`, `search_airports(query='Chicago')`. Answer (abridged):

> Both the Los Angeles and Chicago metropolitan areas are served by multiple airports:
> Los Angeles Area: LAX - Los Angeles International (Primary), BUR - Hollywood Burbank, LGB - Long Beach,
> ONT - Ontario, SNA - John Wayne Orange County. Chicago Area: ORD - O'Hare (Primary), MDW - Midway.
> Which specific airports would you like to compare (e.g., the primary hubs LAX vs. ORD), or would you like to
> compare all of them?

Follow-up **"LAX and ORD"** -> `compare_airports(codes=['LAX', 'ORD'])` -> the usual comparison (LAX 187.6
departures per runway per day on 4 runways vs ORD 143.5 on 8; scores 80.4 vs 87.5).

**"Compare LA and Santa Ana airport congestion levels."** (the assignment's second sample question)
Tools: `search_airports(query='LA')`, `search_airports(query='Santa Ana')`. The agent resolved Santa Ana to SNA,
listed the five Los Angeles airports in a table with LAX marked as primary, and asked which one to compare with
SNA. Follow-up **"LAX"** -> `compare_airports(codes=['LAX', 'SNA'])` -> the same comparison as on 2026-10-19
(LAX 80.4 vs SNA 74.0, SNA's single runway and legal cap from the curated note).
