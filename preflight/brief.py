"""Generate BRIEF.md: what a tech lead would tell the agent before delegating."""

from __future__ import annotations

import re
from pathlib import Path

from . import llm
from .log import block, say
from .scan import Scan, render, scan

BRIEF_SYSTEM = (
    "You are a senior tech lead writing a short delegation brief for a coding agent that has never seen this repo. "
    "Be concrete and terse. Only reference files that appear in the scan. Do not write code."
)

BRIEF_PROMPT = """{scan}

# Issue
{issue}

Write the brief in exactly this markdown structure:

## Start here
Ranked list (max 5) of files to open first, each with one line on why.

## Conventions
Bullets: patterns the fix must follow (naming, typing, error handling, tests location). Only what you can infer from the scan.

## Verify
The exact command to run the tests, and which test(s) would prove the fix.

## Risks
Bullets: what could go wrong, what NOT to touch.

## Size
One of: S (single-file, local change), M (2-3 files or a behaviour change), L (cross-module / design decision).
Then one sentence of rationale.

## Tier
Recommended model tier: cheap | mid | strong. One sentence why. S->cheap, M->cheap or mid, L->strong unless clearly mechanical.
"""


def heuristic_size(s: Scan) -> str:
    """Zero-token fallback / sanity check on the LLM's size call."""
    mods = s.keywords_hit_modules()
    top = s.hits[0].score if s.hits else 0
    if mods <= 1 and top > 0:
        return "S"
    if mods <= 3:
        return "M"
    return "L"


def parse_size_tier(text: str) -> tuple[str, str]:
    size, tier = "?", "?"
    sec = None
    for line in text.splitlines():
        ls = line.strip()
        if ls.startswith("## "):
            sec = ls[3:].strip().lower()
            continue
        if not ls:
            continue
        if sec == "size" and size == "?":
            m = re.match(r"[*_`\s]*([SML])\b", ls)
            if m:
                size = m.group(1)
        elif sec == "tier" and tier == "?":
            for t in ("cheap", "mid", "strong"):
                if t in ls.lower():
                    tier = t
                    break
    return size, tier


def make_brief(root: Path, issue: str, model: str = "haiku") -> tuple[str, llm.LLMResult, Scan]:
    s = scan(root, issue)
    top = ", ".join(h.path for h in s.hits[:3]) or "(no keyword hits)"
    say(f"scan: {s.n_files} files, 0 tokens; test cmd `{s.test_cmd}`; top files by issue keywords: {top}")
    say(f"brief: asking {model} ...")
    res = llm.call(BRIEF_PROMPT.format(scan=render(s), issue=issue.strip()), model=model, system=BRIEF_SYSTEM)
    size, tier = parse_size_tier(res.text)
    header = (
        f"<!-- preflight brief | model={res.model} | cost=${res.cost_usd:.4f} | "
        f"tokens={res.total_tokens} | size={size} tier={tier} | heuristic_size={heuristic_size(s)} -->\n"
    )
    text = header + "# Brief\n\n" + res.text.strip() + "\n"
    say(
        f"brief: size={size} tier={tier} (heuristic {heuristic_size(s)}), ${res.cost_usd:.4f}, {res.duration_ms / 1000:.0f}s"
    )
    block("BRIEF", res.text)
    return text, res, s
