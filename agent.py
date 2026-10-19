"""Gemini tool-calling loop. The model picks tools and narrates; it never computes a number.

Automatic function calling is disabled on purpose: running the loop ourselves gives the UI a
complete trace of every call and result, and turns tool exceptions into data the model can explain.
"""
from __future__ import annotations

import os
import time

from google import genai
from google.genai import errors, types

import agentfiles
import config
import tools

TOOLS = tools.TOOLS
_BY_NAME = {f.__name__: f for f in TOOLS}

# The agent's voice and rules are Markdown (agent/SYSTEM.md); the region names come from config so the two never drift.
SYSTEM_PROMPT = agentfiles.render(agentfiles.read("SYSTEM.md"), regions=", ".join(config.REGIONS)).strip()


def _client() -> genai.Client:
    return genai.Client(api_key=os.environ["GEMINI_API_KEY"])


def _config() -> types.GenerateContentConfig:
    return types.GenerateContentConfig(
        tools=TOOLS,
        system_instruction=SYSTEM_PROMPT,
        temperature=0.2,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )


last_model: str | None = None   # which model produced the most recent response (shown in the UI)


def _with_fallback(call):
    """Run call(model) over config.MODELS.

    Free-tier quotas are per model: 5 requests/minute and a small daily cap. A per-minute 429 gets one
    20 s wait; a daily-cap 429 (or a second per-minute hit) moves on to the next model. 503 = overload.
    """
    global last_model
    last_error = None
    for model in config.MODELS:
        for attempt in range(2):
            try:
                result = call(model)
                last_model = model
                return result
            except errors.APIError as e:
                last_error = e
                if getattr(e, "code", None) not in (429, 503):
                    raise
                if attempt == 0 and "PerDay" not in str(e):
                    time.sleep(20)
                    continue
                break   # next model
    raise RuntimeError(
        f"Gemini free-tier quota exhausted for {', '.join(config.MODELS)}. Daily quotas reset at midnight "
        f"Pacific time; try later or set GEMINI_MODEL to another model. Last error: {last_error}")


def _generate(client: genai.Client, history: list):
    """One model call, falling back across models on quota errors."""
    return _with_fallback(lambda model: client.models.generate_content(model=model, contents=history, config=_config()))


def ask(history: list, text: str, max_iterations: int = 6) -> tuple[str, list[dict], list]:
    """Send one user turn. Returns (answer_text, tool_trace, updated_history)."""
    client = _client()
    history = history + [types.Content(role="user", parts=[types.Part.from_text(text=text)])]
    trace: list[dict] = []
    for _ in range(max_iterations):
        response = _generate(client, history)
        if not response.candidates:
            return "The model returned no answer (safety filter or empty response). Please rephrase.", trace, history
        history.append(response.candidates[0].content)
        if not response.function_calls:
            return response.text or "", trace, history
        parts = []
        for call in response.function_calls:
            args = dict(call.args or {})
            try:
                result = _BY_NAME[call.name](**args)
            except Exception as e:   # the model gets the error as data and can recover or explain
                result = {"error": f"{type(e).__name__}: {e}"}
            trace.append({"tool": call.name, "args": args, "result": result})
            parts.append(types.Part.from_function_response(name=call.name, response={"result": result}))
        history.append(types.Content(role="user", parts=parts))   # Gemini accepts only user/model; function responses travel as "user"
    return "I ran out of tool-call iterations; please narrow the question.", trace, history


def transcribe(audio_bytes: bytes, mime_type: str = "audio/wav") -> str:
    """Speech to text with the same model (voice input bonus)."""
    client = _client()
    r = _with_fallback(lambda model: client.models.generate_content(
        model=model,
        contents=[types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
                  "Transcribe this audio verbatim. Return only the transcript."]))
    return (r.text or "").strip()


if __name__ == "__main__":
    import sys

    from dotenv import load_dotenv

    load_dotenv()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # Windows consoles default to a legacy code page
    answer, trace, _ = ask([], " ".join(sys.argv[1:]) or "Compare LA and Santa Ana airport congestion levels.")
    for t in trace:
        print(f"[tool] {t['tool']}({t['args']})")
    print(f"[model] {last_model}")
    print(answer)
