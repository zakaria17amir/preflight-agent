"""Distill a failed attempt into an enriched brief for the next tier.

Deliberately NOT the raw transcript: a failed transcript left in context anchors the next attempt on the
same wrong path (context contamination). We hand over a structured post-mortem instead.
"""
from __future__ import annotations

from . import llm

HANDOFF_SYSTEM = (
    "You are a senior tech lead. A cheaper engineer just failed to fix an issue. You are writing the handoff "
    "for a stronger engineer who will start fresh. Be terse and concrete. Do not paste the diff; describe it."
)

HANDOFF_PROMPT = """# Issue
{issue}

# Original brief
{brief}

# Failed attempt
{transcript}

Write an updated brief with exactly these sections:

## Start here
Ranked files to open first, revised in light of the failure. Max 5.

## What was tried and why it failed
Bullets. Be specific: which file/function was changed, what the tests still said. Distinguish "wrong location",
"right location, wrong fix", and "fix broke something else".

## Ruled out
Hypotheses the next attempt should NOT re-investigate.

## Verify
The exact test command and the specific test names that must go green.

## Remaining hypotheses
Ranked. The most likely root cause first, with the one line of evidence for it.
"""


def make_handoff(issue: str, brief: str, transcript: str, model: str = "haiku") -> tuple[str, llm.LLMResult]:
    res = llm.call(HANDOFF_PROMPT.format(issue=issue.strip(), brief=brief.strip(), transcript=transcript.strip()),
                   model=model, system=HANDOFF_SYSTEM)
    header = f"<!-- preflight handoff | model={res.model} | cost=${res.cost_usd:.4f} | tokens={res.total_tokens} -->\n"
    return header + "# Brief (v2, after failed attempt)\n\n" + res.text.strip() + "\n", res
