import types as pytypes

import pytest
from google.genai import errors, types

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


class FakeModels:
    def __init__(self, behaviour):
        self.behaviour, self.calls = behaviour, []

    def generate_content(self, model, contents, config):
        self.calls.append(model)
        outcome = self.behaviour[model]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _quota_error(kind):
    return errors.ClientError(429, {"error": {"code": 429, "message": f"quota {kind}", "status": "RESOURCE_EXHAUSTED",
                                              "details": [{"quotaId": f"GenerateRequests{kind}PerProjectPerModel-FreeTier"}]}})


def test_daily_quota_moves_to_next_model(monkeypatch):
    monkeypatch.setattr(agent.config, "MODELS", ["m-a", "m-b"])
    monkeypatch.setattr(agent.time, "sleep", lambda s: None)
    fake = FakeModels({"m-a": _quota_error("PerDay"), "m-b": FakeResponse(text="ok")})
    assert agent._generate(pytypes.SimpleNamespace(models=fake), []).text == "ok"
    assert fake.calls == ["m-a", "m-b"] and agent.last_model == "m-b"


def test_per_minute_quota_waits_once_then_moves_on(monkeypatch):
    monkeypatch.setattr(agent.config, "MODELS", ["m-a", "m-b"])
    sleeps = []
    monkeypatch.setattr(agent.time, "sleep", sleeps.append)
    fake = FakeModels({"m-a": _quota_error("PerMinute"), "m-b": FakeResponse(text="ok")})
    assert agent._generate(pytypes.SimpleNamespace(models=fake), []).text == "ok"
    assert fake.calls == ["m-a", "m-a", "m-b"] and sleeps == [20]


def test_all_models_exhausted_raises_friendly_error(monkeypatch):
    monkeypatch.setattr(agent.config, "MODELS", ["m-a"])
    monkeypatch.setattr(agent.time, "sleep", lambda s: None)
    with pytest.raises(RuntimeError, match="quota exhausted"):
        agent._generate(pytypes.SimpleNamespace(models=FakeModels({"m-a": _quota_error("PerDay")})), [])
