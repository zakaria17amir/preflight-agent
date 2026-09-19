"""Cheap tier first; on failure, hand off (distilled) and escalate."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .brief import make_brief, parse_size_tier
from .handoff import make_handoff
from .log import say
from .progress import NoProgress
from .run import Attempt, attempt
from .scan import render, scan


@dataclass
class Stage:
    name: str
    cost_usd: float
    tokens: int
    seconds: float
    passed: bool | None = None
    model: str = ""


@dataclass
class CascadeResult:
    passed: bool
    stages: list[Stage] = field(default_factory=list)
    attempts: list[Attempt] = field(default_factory=list)
    brief: str = ""
    handoff: str = ""

    @property
    def cost_usd(self) -> float:
        return sum(s.cost_usd for s in self.stages)

    @property
    def tokens(self) -> int:
        return sum(s.tokens for s in self.stages)

    @property
    def final_tier(self) -> str:
        return next((s.model for s in reversed(self.stages) if s.passed is not None), "")

    def summary(self) -> str:
        from .llm import engine
        est = " (est. from list prices)" if engine() == "devin" else ""
        head = f"CASCADE {'PASS' if self.passed else 'FAIL'} total ${self.cost_usd:.4f}{est} {self.tokens} tok [{engine()}]"
        rows = [f"  - {s.name:<10} {s.model:<28} ${s.cost_usd:.4f} {s.tokens:>7} tok {s.seconds:>5.0f}s"
                + ("" if s.passed is None else ("  PASS" if s.passed else "  FAIL")) for s in self.stages]
        return "\n".join([head, *rows])


def _section(md: str, title: str, max_len: int = 220) -> str:
    """First meaningful line under a '## title' heading of a brief/handoff, for one-line step summaries."""
    m = re.search(rf"^##\s*{re.escape(title)}\s*$\n(.*?)(?=^## |\Z)", md, re.M | re.S)
    if not m:
        return ""
    for line in m.group(1).splitlines():
        t = line.strip().lstrip("-*0123456789. ").strip()
        if t:
            return (t[: max_len - 1] + "…") if len(t) > max_len else t
    return ""


def _attempt_summary(a: Attempt) -> str:
    files = sorted({m.group(1) for m in re.finditer(r"^\+\+\+ b/(.+)$", a.diff, re.M)})
    changed = f"changed {', '.join(files[:3])}{'…' if len(files) > 3 else ''}" if files else "made no changes"
    first = next((l.strip() for l in a.agent_summary.splitlines() if l.strip()), "")
    return f"{'PASS' if a.passed else 'FAIL'} — {a.tests.summary}. Agent {changed} in {a.turns} turns. {first}"[:400]


def cascade(root: Path, issue: str, tiers: list[str], test_cmd: str | None = None, use_brief: bool = True,
            use_handoff: bool = True, brief_model: str = "haiku", cheap_max_turns: int | None = None,
            progress=None) -> CascadeResult:
    """Run `tiers` in order. `cheap_max_turns` caps every tier except the last, so a failed cheap attempt stays cheap.
    `progress` (preflight.progress.Progress) gets one start/done per step for the dashboard side panel."""
    p = progress or NoProgress()
    out = CascadeResult(passed=False)
    try:
        p.start("scan", "deterministic repo scan, 0 tokens")
        s = scan(root, issue)
        test_cmd = test_cmd or s.test_cmd
        top = ", ".join(h.path for h in s.hits[:3]) or "no keyword hits"
        p.done(f"{s.n_files} files. Test cmd: {s.test_cmd}. Top files for this issue: {top}.", cost=0.0)

        brief_text = None
        if use_brief:
            p.start("brief", f"{brief_model} writes the delegation brief")
            brief_text, bres, s = make_brief(root, issue, model=brief_model)
            out.brief = brief_text
            out.stages.append(Stage("brief", bres.cost_usd, bres.total_tokens, bres.duration_ms / 1000, model=bres.model))
            size, tier = parse_size_tier(brief_text)
            p.done(f"Size {size}, tier {tier}. Start here: {_section(brief_text, 'Start here')}", cost=bres.cost_usd)

        for i, tier in enumerate(tiers):
            is_last = i + 1 == len(tiers)
            budget = None if is_last else cheap_max_turns
            p.start(f"attempt{i+1}", f"{tier}{f', budget {budget} tool calls' if budget else ''}, "
                                     f"{'with brief v2' if i and use_handoff else 'with brief' if brief_text else 'cold'}")
            a = attempt(root, issue, brief=brief_text, model=tier, test_cmd=test_cmd, max_turns=budget)
            out.attempts.append(a)
            out.stages.append(Stage(f"attempt{i+1}", a.cost_usd, a.tokens, a.seconds, passed=a.passed, model=a.model))
            p.done(_attempt_summary(a), cost=a.cost_usd, ok=a.passed)
            if a.passed:
                out.passed = True
                say(f"solved at tier {i+1} ({tier}); total so far ${out.cost_usd:.4f}")
                break
            if is_last:
                say(f"tier {i+1} ({tier}) failed and it was the last tier")
                break
            say(f"tier {i+1} ({tier}) failed -> escalating to {tiers[i+1]} "
                f"{'with handoff' if use_handoff else 'with a clean restart (original brief)'}")
            if use_handoff:
                p.start("handoff", f"{brief_model} distills the failure for {tiers[i+1]}")
                h_text, hres = make_handoff(issue, brief_text or "(no brief was given)", a.transcript_for_handoff(),
                                            model=brief_model, scan_text=render(s, max_tree=60))
                out.handoff = h_text
                brief_text = h_text
                out.stages.append(Stage("handoff", hres.cost_usd, hres.total_tokens, hres.duration_ms / 1000, model=hres.model))
                p.done(f"Why it failed: {_section(h_text, 'What was tried and why it failed')} "
                       f"Next: {_section(h_text, 'Remaining hypotheses')}", cost=hres.cost_usd)

        p.finish(out.passed, f"{'Solved' if out.passed else 'Not solved'} at {out.final_tier or 'no tier'} "
                             f"for ${out.cost_usd:.4f} across {len(out.attempts)} attempt(s).")
    except Exception as e:
        p.fail(repr(e))
        raise
    return out
