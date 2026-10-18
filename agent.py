"""Gemini tool-calling loop. The model picks tools and narrates; it never computes a number.

Automatic function calling is disabled on purpose: running the loop ourselves gives the UI a
complete trace of every call and result, and turns tool exceptions into data the model can explain.
"""
from __future__ import annotations

import os
import time

from google import genai
from google.genai import errors, types

import config
import tools

TOOLS = [tools.search_airports, tools.rank_airports, tools.airport_profile,
         tools.compare_airports, tools.long_haul_share, tools.live_status]
_BY_NAME = {f.__name__: f for f in TOOLS}

SYSTEM_PROMPT = """You are the Airport Investment Intelligence Agent: an analyst assistant for a firm that invests in US airport modernization. You help analysts find airports where added flight and passenger capacity would be most valuable, and you explain why.

Hard rules:
1. Every number, ranking or airport fact you state must come from a tool result in this conversation. If you have not called a tool for it, call one. Never recall or estimate figures.
2. Resolve airport names to IATA codes. For ambiguous city names use the primary commercial airport and say which you chose ("LA" -> LAX, "Santa Ana" -> SNA, "Anchorage" -> ANC, "Boston" -> BOS). When unsure, call search_airports.
3. Named regions you can pass to rank_airports: new_england, mid_atlantic, southeast, midwest, texas, mountain_west, west_coast, pacific_northwest, alaska_hawaii. For anything else pass explicit two-letter states.
4. Answer structure: (a) the direct answer in one or two sentences; (b) a compact markdown table of the key numbers; (c) the reasoning, built from the score breakdown (component, percentile, weight, contribution) or the unmet-demand flags; (d) a short "Assumptions & caveats" list: data year and source from meta, every caveat the tool returned, and that the score measures capacity-expansion opportunity, not profitability.
5. Report percentages exactly as the *_pct fields give them (one decimal). Do not do arithmetic beyond comparing numbers.
6. Curated notes are hand-written context with a source; say "curated note" when you use one. Live status (FAA, OpenSky) is a snapshot and is never part of the score; say so when you mention it.
7. Follow-up questions refer to the airports and filters already discussed unless the user says otherwise.
8. If a tool returns an error, explain it plainly and suggest what to ask instead.
Be concise and specific. No marketing language."""


def _client() -> genai.Client:
    return genai.Client(api_key=os.environ["GEMINI_API_KEY"])


def _config() -> types.GenerateContentConfig:
    return types.GenerateContentConfig(
        tools=TOOLS,
        system_instruction=SYSTEM_PROMPT,
        temperature=0.2,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )


def _generate(client: genai.Client, history: list):
    """One model call with retries on rate limit / overload."""
    for attempt in range(3):
        try:
            return client.models.generate_content(model=config.MODEL, contents=history, config=_config())
        except errors.APIError as e:
            if getattr(e, "code", None) in (429, 503) and attempt < 2:
                time.sleep(2 * 2 ** attempt)
                continue
            raise


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
        history.append(types.Content(role="tool", parts=parts))
    return "I ran out of tool-call iterations; please narrow the question.", trace, history


def transcribe(audio_bytes: bytes, mime_type: str = "audio/wav") -> str:
    """Speech to text with the same model (voice input bonus)."""
    r = _client().models.generate_content(
        model=config.MODEL,
        contents=[types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
                  "Transcribe this audio verbatim. Return only the transcript."])
    return (r.text or "").strip()


if __name__ == "__main__":
    import sys

    from dotenv import load_dotenv

    load_dotenv()
    answer, trace, _ = ask([], " ".join(sys.argv[1:]) or "Compare LA and Santa Ana airport congestion levels.")
    for t in trace:
        print(f"[tool] {t['tool']}({t['args']})")
    print(answer)
