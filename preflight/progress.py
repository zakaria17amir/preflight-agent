"""Step tracker for a running cascade. Writes bench/results/progress.json on every transition; the dashboard
polls it and renders the side panel ("which step is it on, what did the last step conclude").
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / "bench" / "results" / "progress.json"

STEPS = ["scan", "brief", "attempt1", "handoff", "attempt2", "attempt3", "patch"]


class Progress:
    def __init__(self, title: str, repo: str, issue: str, engine: str, tiers: list[str]):
        self.state = dict(
            title=title,
            repo=repo,
            issue=issue[:300],
            engine=engine,
            tiers=tiers,
            status="running",
            started=time.time(),
            updated=time.time(),
            finished=None,
            steps=[],
            total_cost=0.0,
            passed=None,
        )
        self._write()

    def _write(self) -> None:
        self.state["updated"] = time.time()
        PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = PATH.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self.state, indent=1), encoding="utf-8")
        os.replace(tmp, PATH)

    def start(self, step: str, detail: str = "") -> None:
        self.state["steps"].append(
            dict(name=step, status="running", detail=detail, summary="", started=time.time(), seconds=None, cost=None)
        )
        self._write()

    def done(self, summary: str, cost: float | None = None, ok: bool | None = None) -> None:
        s = self.state["steps"][-1]
        s.update(
            status="done" if ok is None else ("pass" if ok else "fail"),
            summary=summary[:600],
            seconds=round(time.time() - s["started"], 1),
            cost=cost,
        )
        if cost:
            self.state["total_cost"] = round(self.state["total_cost"] + cost, 5)
        self._write()

    def finish(self, passed: bool, summary: str) -> None:
        self.state.update(status="finished", finished=time.time(), passed=passed, final_summary=summary[:600])
        self._write()

    def fail(self, error: str) -> None:
        if self.state["steps"] and self.state["steps"][-1]["status"] == "running":
            self.done(f"error: {error}", ok=False)
        self.state.update(status="error", finished=time.time(), passed=False, final_summary=error[:600])
        self._write()


class NoProgress:
    """Drop-in when no tracking is wanted (the bench)."""

    def start(self, *a, **k):
        pass

    def done(self, *a, **k):
        pass

    def finish(self, *a, **k):
        pass

    def fail(self, *a, **k):
        pass
