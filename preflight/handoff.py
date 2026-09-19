"""Distill a failed attempt into an enriched brief for the next tier.

Deliberately NOT the raw transcript: a failed transcript left in context anchors the next attempt on the
same wrong path (context contamination). We hand over a structured post-mortem instead.
"""

from __future__ import annotations

import re

from . import llm
from .log import block, say

HANDOFF_SYSTEM = (
    "You are a senior tech lead. A cheaper engineer just failed to fix an issue. You are writing the handoff "
    "for a stronger engineer who will start fresh. Be terse and concrete. Do not paste the diff; describe it. "
    "You have NO tools: you cannot read files, run commands, or search. Work only from the material given. "
    "Never invent function names, line numbers, or file contents that do not appear in the material; if you don't "
    "know, say what the next engineer should check. Start directly with the first '## ' section; no title line."
)

HANDOFF_PROMPT = """# Issue
{issue}

# Repo scan (deterministic, ground truth for file names)
{scan}

# Original brief
{brief}

# Failed attempt
{transcript}

Write an updated brief with exactly these sections:

## Start here
Ranked files to open first, revised in light of the failure. Max 5. Only files that appear in the scan.

## What was tried and why it failed
Bullets. Be specific: which file/function was changed, what the tests still said. Distinguish "wrong location",
"right location, wrong fix", "fix broke something else", and "ran out of budget before changing anything".

## Ruled out
Hypotheses the next attempt should NOT re-investigate. If the attempt changed nothing, say that nothing is ruled out.

## Verify
The exact test command and the specific test names that must go green.

## Remaining hypotheses
Ranked. The most likely root cause first, with the one line of evidence for it from the material above.
"""

_TOOLCALL_RE = re.compile(
    r"<function_calls>.*?</function_calls>|<invoke\b.*?</invoke>|</?function_calls>|</?invoke[^>]*>", re.S
)


def sanitize(text: str) -> tuple[str, bool]:
    """Strip hallucinated tool-call markup from a no-tools completion. Returns (clean_text, had_markup)."""
    clean, n = _TOOLCALL_RE.subn("", text)
    clean = re.sub(r"^\s*I'll (analy[sz]e|look at|read|check)[^\n]*\n", "", clean, flags=re.I)
    return clean.strip(), n > 0


def make_handoff(
    issue: str, brief: str, transcript: str, model: str = "haiku", scan_text: str = "(not provided)"
) -> tuple[str, llm.LLMResult]:
    say(f"handoff: distilling the failed attempt with {model} ...")
    res = llm.call(
        HANDOFF_PROMPT.format(
            issue=issue.strip(), scan=scan_text.strip(), brief=brief.strip(), transcript=transcript.strip()
        ),
        model=model,
        system=HANDOFF_SYSTEM,
    )
    body, had_markup = sanitize(res.text)
    if had_markup:
        say("handoff: model emitted fake tool calls (it has no tools); stripped them")
    header = f"<!-- preflight handoff | model={res.model} | cost=${res.cost_usd:.4f} | tokens={res.total_tokens} -->\n"
    say(f"handoff: ${res.cost_usd:.4f}, {res.duration_ms / 1000:.0f}s")
    block("HANDOFF (brief v2 for the next tier)", body)
    return header + "# Brief (v2, after failed attempt)\n\n" + body + "\n", res
