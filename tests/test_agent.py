import types as pytypes

from google.genai import types

import agent


class FakeResponse:
    def __init__(self, text=None, calls=None):
        self.text = text
        self.function_calls = calls or []
        part = types.Part.from_text(text=text) if text else types.Part.from_function_call(name=calls[0].name, args=calls[0].args)
        self.candidates = [pytypes.SimpleNamespace(content=types.Content(role="model", parts=[part]))]


def test_ask_runs_tool_then_returns_text(monkeypatch):
    calls = [FakeResponse(calls=[types.FunctionCall(name="rank_airports", args={"region": "new_england", "top_n": 3})]),
             FakeResponse(text="BOS leads.")]
    monkeypatch.setattr(agent, "_generate", lambda client, history: calls.pop(0))
    monkeypatch.setattr(agent, "_client", lambda: None)
    monkeypatch.setitem(agent._BY_NAME, "rank_airports", lambda **kw: {"ranking": [{"code": "BOS"}], "args_seen": kw})
    answer, trace, history = agent.ask([], "New England candidates?")
    assert answer == "BOS leads."
    assert trace == [{"tool": "rank_airports", "args": {"region": "new_england", "top_n": 3},
                      "result": {"ranking": [{"code": "BOS"}], "args_seen": {"region": "new_england", "top_n": 3}}}]
    assert [c.role for c in history] == ["user", "model", "user", "model"]
    assert history[2].parts[0].function_response.name == "rank_airports"


def test_tool_exception_is_returned_to_model_not_raised(monkeypatch):
    calls = [FakeResponse(calls=[types.FunctionCall(name="airport_profile", args={"code": "SFO"})]),
             FakeResponse(text="Sorry, that failed.")]
    monkeypatch.setattr(agent, "_generate", lambda client, history: calls.pop(0))
    monkeypatch.setattr(agent, "_client", lambda: None)

    def boom(**kw):
        raise RuntimeError("disk on fire")
    monkeypatch.setitem(agent._BY_NAME, "airport_profile", boom)
    answer, trace, _ = agent.ask([], "SFO?")
    assert trace[0]["result"] == {"error": "RuntimeError: disk on fire"} and answer == "Sorry, that failed."


def test_iteration_cap(monkeypatch):
    monkeypatch.setattr(agent, "_generate", lambda client, history: FakeResponse(
        calls=[types.FunctionCall(name="live_status", args={"code": "SFO"})]))
    monkeypatch.setattr(agent, "_client", lambda: None)
    monkeypatch.setitem(agent._BY_NAME, "live_status", lambda **kw: {"ok": True})
    answer, trace, _ = agent.ask([], "loop", max_iterations=3)
    assert len(trace) == 3 and "ran out" in answer
