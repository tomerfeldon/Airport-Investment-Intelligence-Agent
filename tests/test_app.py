"""UI plumbing via Streamlit's AppTest: no browser, no model - agent.ask is faked."""
import pathlib

import pytest
from streamlit.testing.v1 import AppTest

import agent
import live
import tools

APP = str(pathlib.Path(__file__).resolve().parents[1] / "app.py")
EXAMPLE_1 = "Which airports in New England are strong candidates for terminal expansion?"


@pytest.fixture
def at(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "dummy-for-apptest")
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: False)
    monkeypatch.setattr(live, "faa_status", lambda: {"updated": "t", "entries": {}})
    monkeypatch.setattr(live, "opensky_departures", lambda icao: {"status": "not configured"})
    calls = []

    def fake_ask(history, text, max_iterations=6):
        calls.append(text)
        trace = [{"tool": "rank_airports", "args": {"region": "new_england"},
                  "result": tools.rank_airports(region="new_england")}]
        return f"Answer to: {text}", trace, history + ["turn"]

    monkeypatch.setattr(agent, "ask", fake_ask)
    return AppTest.from_file(APP, default_timeout=60).run(), calls


def test_renders_title_sidebar_and_examples(at):
    app, _ = at
    assert not app.exception
    assert "Airport Investment Intelligence Agent" in app.title[0].value
    labels = [b.label for b in app.sidebar.button]
    assert EXAMPLE_1 in labels and "Clear chat" in labels
    assert "percentile rank" in " ".join(m.value for m in app.sidebar.markdown)


def test_example_button_runs_agent_and_shows_trace(at):
    app, calls = at
    app.sidebar.button[0].click().run()
    assert not app.exception
    assert calls == [EXAMPLE_1]
    assert any("Answer to:" in m.value for m in app.markdown)
    assert any("Data behind this answer" in e.label for e in app.expander)
    assert len(app.chat_message) == 2


def test_chat_input_sends_message(at):
    app, calls = at
    app.chat_input[0].set_value("Compare LAX and SNA").run()
    assert not app.exception and calls == ["Compare LAX and SNA"]


def test_missing_key_shows_error_not_traceback(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: False)
    app = AppTest.from_file(APP).run()
    assert not app.exception and app.error and "GEMINI_API_KEY" in app.error[0].value
