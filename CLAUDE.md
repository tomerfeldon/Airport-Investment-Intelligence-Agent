# Airport Investment Intelligence Agent

Chat agent that ranks US airports as capacity-expansion investment opportunities. Deterministic scoring over
public data; Gemini only routes questions to six tools and narrates their results. `DESIGN.md` holds the
methodology, data limits and tradeoffs; `README.md` the quick start.

## Run and test

- `.venv\Scripts\python.exe -m streamlit run app.py` - needs `GEMINI_API_KEY` in `.env` (copy `.env.example`)
- `.venv\Scripts\python.exe -m pytest` - 42 tests; no network, no model calls (the model is always faked)
- `.venv\Scripts\python.exe agent.py "Compare LA and Santa Ana airport congestion levels."` - one question on the CLI with its tool trace
- `.venv\Scripts\python.exe scripts/fetch_data.py` - rebuilds `data/` from BTS TranStats and OurAirports; slow, and the output is committed, so run it only to refresh data

## Map

- `agent/` - the agent definition, in Markdown and loaded at runtime: `SYSTEM.md` (prompt and rules), `tools.md` (tool descriptions, applied as docstrings), `methodology.md` (the score explained; also the sidebar text), `caveats.md` (every sentence a tool attaches to a result), `examples.md` (sidebar questions)
- `agentfiles.py` - the loader for `agent/*.md` and `data/airport_notes.md`; fails at import when `tools.md` and `tools.py` disagree
- `config.py` - every tunable: years, universe threshold, score weights, regions, model fallback list
- `metrics.py` - pure functions over DataFrames: metrics, score, breakdown, long-haul share, unmet-demand flags. No LLM here.
- `tools.py` - the six functions the model may call. Each returns a JSON-serializable dict with `meta` and `caveats` and never raises.
- `agent.py` - the Gemini tool loop (manual, at most 6 iterations, temperature 0.2) and the system prompt
- `live.py` - FAA NAS status and optional OpenSky overlay; failures come back as `"unavailable"`, never as exceptions
- `app.py` - Streamlit chat. Rendering only; no logic belongs here.
- `data/` - committed extracts (T-100 2024-2025, OurAirports airports and runways) and `airport_notes.md`, hand-curated facts with a source URL each

## Rules that keep the product honest

- Every number the user sees comes from a tool result. Never let the model compute, estimate or recall a figure; if a question needs a new number, add a tool.
- A tool returns `meta` (data year, source, universe size) and `caveats`, and the prompt makes the model repeat them. Keep that contract when adding or changing a tool.
- Live signals (FAA, OpenSky) are shown next to the score and are never part of it. A ranking that changes with the weather is not a ranking.
- Tools are read-only: nothing writes, sends or pays. This bounds what a prompt injection can do.
- No model-facing or user-facing prose in `.py` files. The prompt, tool descriptions, methodology text, caveats, example questions and curated notes live in `agent/*.md` and `data/airport_notes.md`; code reads them through `agentfiles.py`. Exceptions: error strings (diagnostics) and UI chrome such as the title, button labels and placeholders in `app.py`.
- The tool descriptions in `agent/tools.md` plus the type hints are the schema Gemini sees. Changing a description changes model behavior; check the four sample questions afterwards.
- Curated notes are labeled as such in answers. Do not add airport facts anywhere else in code.

## When the score changes

Changing `config.WEIGHTS`, a score component or `UNIVERSE_MIN_PASSENGERS` stales all of these: expectations in
`tests/test_metrics.py` and `tests/test_tools.py`, the worked example and national top five in `DESIGN.md` section 2.6,
numbers quoted in `README.md`, and `docs/sample-answers.md`. The sidebar and the methodology the model receives render
from `agent/methodology.md` with the current config values, so they follow automatically unless the wording must change.
Rank-diff the old and new tables first (Spearman between rankings, airports that move more than 10 places) and keep the
diff in the commit message.

## Environment and style

- Windows, venv in `.venv`. On the author's PC Application Control blocks pyarrow, so no `st.dataframe` or `st.table`; render tables with `md_table` in `app.py`.
- Gemini free tier is about 5 requests per minute and 20 per day per model; `agent.py` falls back through `config.MODELS`. Tests never call Gemini. Live runs cost quota, so batch them and prefer the CLI.
- Function responses go back to Gemini as role `"user"`; the API rejects role `"tool"`.
- Secrets live only in `.env`, which is gitignored. Never print or commit them.
- Plain hyphens only; no em dashes or en dashes in code, docs or commit messages. One-line commit messages.
