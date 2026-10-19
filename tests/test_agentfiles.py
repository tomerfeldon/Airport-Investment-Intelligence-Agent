"""The agent definition is Markdown. These tests cover the loader and the sync between agent/*.md and the code."""
import pytest

import agent
import agentfiles
import config
import tools

MD = """# ignored preamble

## alpha
First body line.
Second line.

## beta
- one
- two
"""


def test_sections_and_bullets():
    s = agentfiles.sections(MD)
    assert list(s) == ["alpha", "beta"]
    assert s["alpha"] == "First body line.\nSecond line."
    assert agentfiles.bullets(s["beta"]) == ["one", "two"]


def test_render_supports_format_specs():
    assert agentfiles.render("at least {n:,} passengers in {year}", n=500_000, year=2025) == "at least 500,000 passengers in 2025"


def test_notes_parser(tmp_path):
    p = tmp_path / "notes.md"
    p.write_text("""# Notes

## AAA

### constraint
Line one of the note.
Line two.
source: https://example.com/a
verified: 2026-01-01

### context
Short context.
source: https://example.com/b
verified: 2026-01-02

## BBB

### context
Only note.
source: https://example.com/c
verified: 2026-01-03
""", encoding="utf-8")
    notes = agentfiles.notes(p)
    assert set(notes) == {"AAA", "BBB"} and len(notes["AAA"]) == 2
    assert notes["AAA"][0] == {"type": "constraint", "text": "Line one of the note. Line two.",
                               "source": "https://example.com/a", "verified": "2026-01-01"}
    assert notes["BBB"][0]["type"] == "context" and notes["BBB"][0]["text"] == "Only note."


def test_apply_tool_docs_sets_docstrings_and_detects_drift(monkeypatch):
    def f_one():
        pass

    def f_two():
        pass

    monkeypatch.setattr(agentfiles, "read", lambda name: "## f_one\nDoes one.\n\nArgs:\n    x: {regions}\n\n## f_two\nDoes two.\n")
    agentfiles.apply_tool_docs([f_one, f_two], regions="r1, r2")
    assert f_one.__doc__ == "Does one.\n\nArgs:\n    x: r1, r2" and f_two.__doc__ == "Does two."
    with pytest.raises(RuntimeError, match=r"missing \['<lambda>'\]"):
        agentfiles.apply_tool_docs([f_one, f_two, lambda: None])
    with pytest.raises(RuntimeError, match=r"extra \['f_two'\]"):
        agentfiles.apply_tool_docs([f_one])


def test_real_tools_have_markdown_descriptions():
    assert [f.__name__ for f in agent.TOOLS] == [f.__name__ for f in tools.TOOLS]
    for f in tools.TOOLS:
        assert f.__doc__ and "Args:" in f.__doc__ and "{" not in f.__doc__
    assert "new_england" in tools.rank_airports.__doc__


def test_system_prompt_rendered_from_markdown():
    assert "{" not in agent.SYSTEM_PROMPT and "}" not in agent.SYSTEM_PROMPT
    for region in config.REGIONS:
        assert region in agent.SYSTEM_PROMPT
    assert "הנחות והסתייגויות" in agent.SYSTEM_PROMPT


def test_every_caveat_key_used_in_code_exists():
    import pathlib
    import re
    keys = set(agentfiles.sections(agentfiles.read("caveats.md")))
    used = set()
    for name in ("tools.py", "live.py"):
        used |= set(re.findall(r'(?:_c|agentfiles\.caveat)\("([a-z_]+)"', pathlib.Path(name).read_text(encoding="utf-8")))
    assert used and used <= keys, used - keys
