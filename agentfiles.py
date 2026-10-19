"""Loads the agent definition from agent/*.md and data/airport_notes.md.

The agent is Markdown: the system prompt, the tool descriptions, the methodology text, every caveat sentence,
the example questions and the curated notes. Python only executes. Nothing user-facing or model-facing is
written as a literal in a .py file; it is read from here.
"""
from __future__ import annotations

import functools
import pathlib
import re

AGENT_DIR = pathlib.Path(__file__).resolve().parent / "agent"


@functools.lru_cache(maxsize=None)
def read(name: str) -> str:
    return (AGENT_DIR / name).read_text(encoding="utf-8")


def sections(text: str) -> dict[str, str]:
    """{"heading": "body"} for every level-2 heading; text before the first heading is ignored."""
    out: dict[str, str] = {}
    key, buf = None, []
    for line in text.splitlines():
        if line.startswith("## "):
            if key is not None:
                out[key] = "\n".join(buf).strip()
            key, buf = line[3:].strip(), []
        elif key is not None:
            buf.append(line)
    if key is not None:
        out[key] = "\n".join(buf).strip()
    return out


def bullets(text: str) -> list[str]:
    return [line[2:].strip() for line in text.splitlines() if line.startswith("- ")]


def render(text: str, **values) -> str:
    """str.format, so placeholders can carry format specs such as {universe_min_passengers:,}."""
    return text.format(**values)


def caveat(key: str, **values) -> str:
    return render(sections(read("caveats.md"))[key], **values)


def notes(path: pathlib.Path | str) -> dict[str, list[dict]]:
    """Curated notes: '## CODE' per airport, '### type' per note, 'source:'/'verified:' lines, the rest is the text."""
    out: dict[str, list[dict]] = {}
    for code, body in sections(pathlib.Path(path).read_text(encoding="utf-8")).items():
        items = []
        for block in re.split(r"^### ", body, flags=re.M)[1:]:
            kind, _, rest = block.partition("\n")
            note, text_lines = {"type": kind.strip()}, []
            for line in rest.splitlines():
                m = re.match(r"^(source|verified):\s*(.+)$", line.strip())
                if m:
                    note[m[1]] = m[2].strip()
                elif line.strip():
                    text_lines.append(line.strip())
            note["text"] = " ".join(text_lines)
            items.append(note)
        out[code.strip()] = items
    return out


def apply_tool_docs(functions, **values) -> None:
    """Set each tool's docstring from agent/tools.md. A function without a section, or a section without a
    function, is a startup error rather than a silent drift between what the model is told and what runs."""
    docs = sections(read("tools.md"))
    names = {f.__name__ for f in functions}
    missing, extra = names - set(docs), set(docs) - names
    if missing or extra:
        raise RuntimeError(f"agent/tools.md is out of sync with tools.py: missing {sorted(missing)}, extra {sorted(extra)}")
    for f in functions:
        f.__doc__ = render(docs[f.__name__], **values)
