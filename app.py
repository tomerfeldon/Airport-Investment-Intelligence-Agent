"""Streamlit chat UI. All intelligence is in agent.py / tools.py; this file only renders."""
import os

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

import agent        # noqa: E402  (after load_dotenv so GEMINI_API_KEY is visible)
import agentfiles   # noqa: E402
import config       # noqa: E402
import live         # noqa: E402
import tools        # noqa: E402

st.set_page_config(page_title="Airport Investment Intelligence", page_icon="✈️", layout="wide")
st.markdown("<style>[data-testid='stChatMessageContent'] :is(p, li, td, th, h1, h2, h3, h4) {unicode-bidi: plaintext; text-align: start;}</style>", unsafe_allow_html=True)   # Hebrew answers read right-to-left, English stays left-to-right

EXAMPLES = agentfiles.bullets(agentfiles.read("examples.md"))

if not os.environ.get("GEMINI_API_KEY"):
    st.error("GEMINI_API_KEY is not set. Copy .env.example to .env and add a free key from https://aistudio.google.com/apikey")
    st.stop()
try:
    table, _ = tools._table()
except FileNotFoundError:
    st.error("Data files are missing. Run:  python scripts/fetch_data.py")
    st.stop()

ss = st.session_state
ss.setdefault("history", [])    # Gemini contents
ss.setdefault("messages", [])   # what we render


KEY_COLS = ["code", "name", "state", "score", "passengers", "load_factor_pct", "runways",
            "departures_per_runway_per_day", "growth_yoy_pct"]


def md_table(rows: list[dict], columns: list[str]) -> str:
    """Plain markdown table. st.dataframe/st.table need pyarrow, which locked-down machines may block."""
    def fmt(v):
        if isinstance(v, float):
            return f"{v:,.0f}" if v.is_integer() else f"{v:,.1f}"
        return "" if v is None else str(v)
    head = "| " + " | ".join(columns) + " |\n|" + "---|" * len(columns) + "\n"
    return head + "\n".join("| " + " | ".join(fmt(r.get(c)) for c in columns) + " |" for r in rows)


def render_trace(trace: list[dict]) -> None:
    """The deterministic data behind an answer: every tool call with its arguments and result."""
    if not trace:
        return
    with st.expander(f"Data behind this answer · {len(trace)} tool call(s)"):
        for t in trace:
            args = ", ".join(f"{k}={v!r}" for k, v in t["args"].items())
            st.markdown(f"`{t['tool']}({args})`")
            res = t["result"]
            rows = (res.get("ranking") or res.get("airports")) if isinstance(res, dict) else None
            if rows:
                st.markdown(md_table(rows, [c for c in KEY_COLS if c in rows[0]]))
            st.json(res, expanded=False)


with st.sidebar:
    st.header("How the score works")
    st.markdown(tools.methodology(table)["text"])   # the same text the model receives, from agent/methodology.md
    st.caption(
        f"Data: BTS T-100 {config.YEARS[0]}-{config.YEARS[-1]} · OurAirports runways · "
        f"FAA NAS status (live) · OpenSky ({'configured' if live.opensky_configured() else 'not configured'})")
    st.subheader("Try")
    for q in EXAMPLES:
        if st.button(q):
            ss.pending = q
    if st.button("Clear chat"):
        ss.history, ss.messages = [], []
        st.rerun()

st.title("✈️ Airport Investment Intelligence Agent")
st.caption("Deterministic scoring over public aviation data; the model only routes questions to tools and explains the results.")

for m in ss.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])
        render_trace(m.get("trace", []))
        if m.get("model"):
            st.caption(f"answered by {m['model']}")

audio = st.audio_input("Or ask by voice")
if audio is not None and audio.getvalue() != ss.get("last_audio"):
    ss.last_audio = audio.getvalue()                 # the widget keeps returning the same clip; send it once
    with st.spinner("Transcribing…"):
        try:
            ss.pending = agent.transcribe(ss.last_audio, audio.type or "audio/wav")
        except Exception as e:
            st.warning(f"Transcription failed: {e}")

prompt = st.chat_input("Ask about US airport capacity, congestion or demand…") or ss.pop("pending", None)
if prompt:
    ss.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        with st.spinner("Querying data…"):
            try:
                answer, trace, ss.history = agent.ask(ss.history, prompt)
            except Exception as e:   # model/network failure: show it, keep the chat alive
                answer, trace = f"The model call failed: {e}. Check the API key and try again in a minute.", []
        st.markdown(answer)
        render_trace(trace)
        if agent.last_model:
            st.caption(f"answered by {agent.last_model}")
    ss.messages.append({"role": "assistant", "content": answer, "trace": trace, "model": agent.last_model})
