"""Cheap tier first; on failure, hand off (distilled) and escalate."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .brief import make_brief
from .handoff import make_handoff
from .log import say
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


def cascade(root: Path, issue: str, tiers: list[str], test_cmd: str | None = None, use_brief: bool = True,
            use_handoff: bool = True, brief_model: str = "haiku", cheap_max_turns: int | None = None) -> CascadeResult:
    """Run `tiers` in order. `cheap_max_turns` caps every tier except the last, so a failed cheap attempt stays cheap."""
    s = scan(root, issue)
    test_cmd = test_cmd or s.test_cmd
    out = CascadeResult(passed=False)
    brief_text = None
    if use_brief:
        brief_text, bres, s = make_brief(root, issue, model=brief_model)
        out.brief = brief_text
        out.stages.append(Stage("brief", bres.cost_usd, bres.total_tokens, bres.duration_ms / 1000, model=bres.model))
    for i, tier in enumerate(tiers):
        is_last = i + 1 == len(tiers)
        a = attempt(root, issue, brief=brief_text, model=tier, test_cmd=test_cmd,
                    max_turns=None if is_last else cheap_max_turns)
        out.attempts.append(a)
        out.stages.append(Stage(f"attempt{i+1}", a.cost_usd, a.tokens, a.seconds, passed=a.passed, model=a.model))
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
            h_text, hres = make_handoff(issue, brief_text or "(no brief was given)", a.transcript_for_handoff(),
                                        model=brief_model, scan_text=render(s, max_tree=60))
            out.handoff = h_text
            brief_text = h_text
            out.stages.append(Stage("handoff", hres.cost_usd, hres.total_tokens, hres.duration_ms / 1000, model=hres.model))
    return out
