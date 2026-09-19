"""Run the experiment: for each seeded bug, three arms.

  A  cold_strong     : sonnet, issue only            (the "just use the expensive model" baseline)
  B  brief_cheap     : haiku,  issue + brief          (does orientation let a cheap model do it?)
  C  cascade         : brief -> haiku -> handoff -> sonnet   (start cheap, escalate informed)

Writes bench/results/results.json and prints a markdown table. Resumable: skips (bug, arm) pairs already done.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from bugs import BUGS, apply_bug  # noqa: E402
from preflight.cascade import cascade  # noqa: E402
from preflight.run import attempt, fresh_copy  # noqa: E402
from preflight.brief import make_brief  # noqa: E402

ROOT = Path(__file__).resolve().parent
TARGET = ROOT / "target"
RESULTS = ROOT / "results"
TEST_CMD = "python -m pytest -q -x"


def buggy_copy(bug: str) -> tuple[Path, str]:
    wd = fresh_copy(TARGET)
    issue = apply_bug(wd, bug)
    # commit the bug as the base so `git diff` shows only the agent's change
    import subprocess
    subprocess.run(["git", "add", "-A"], cwd=wd, check=True)
    subprocess.run(["git", "-c", "user.email=p@f", "-c", "user.name=preflight", "commit", "-qm", "bug"], cwd=wd, check=True)
    return wd, issue


def arm_cold_strong(bug: str, model: str) -> dict:
    wd, issue = buggy_copy(bug)
    a = attempt(wd, issue, brief=None, model=model, test_cmd=TEST_CMD, workdir=wd)
    return dict(passed=a.passed, cost=a.cost_usd, tokens=a.tokens, turns=a.turns, seconds=a.seconds,
                stages=[dict(name="attempt1", model=a.model, cost=a.cost_usd, tokens=a.tokens, passed=a.passed)],
                tests=a.tests.summary, summary=a.agent_summary[:600])


def arm_brief_cheap(bug: str, model: str) -> dict:
    wd, issue = buggy_copy(bug)
    brief, bres, _ = make_brief(wd, issue, model="haiku")
    a = attempt(wd, issue, brief=brief, model=model, test_cmd=TEST_CMD, workdir=wd)
    return dict(passed=a.passed, cost=a.cost_usd + bres.cost_usd, tokens=a.tokens + bres.total_tokens, turns=a.turns,
                seconds=a.seconds + bres.duration_ms / 1000,
                stages=[dict(name="brief", model=bres.model, cost=bres.cost_usd, tokens=bres.total_tokens),
                        dict(name="attempt1", model=a.model, cost=a.cost_usd, tokens=a.tokens, passed=a.passed)],
                tests=a.tests.summary, summary=a.agent_summary[:600], brief=brief)


def arm_cascade(bug: str, tiers: list[str]) -> dict:
    wd, issue = buggy_copy(bug)
    # cascade() makes its own fresh copies per attempt from `root`; give it the buggy tree as root.
    r = cascade(wd, issue, tiers=tiers, test_cmd=TEST_CMD)
    return dict(passed=r.passed, cost=r.cost_usd, tokens=r.tokens, turns=sum(a.turns for a in r.attempts),
                seconds=sum(s.seconds for s in r.stages),
                stages=[dict(name=s.name, model=s.model, cost=s.cost_usd, tokens=s.tokens, passed=s.passed) for s in r.stages],
                tests=r.attempts[-1].tests.summary, summary=r.attempts[-1].agent_summary[:600],
                brief=r.brief, handoff=r.handoff, final_tier=r.final_tier)


ARMS = {
    "A_cold_strong": lambda bug, cfg: arm_cold_strong(bug, cfg["strong"]),
    "B_brief_cheap": lambda bug, cfg: arm_brief_cheap(bug, cfg["cheap"]),
    "C_cascade": lambda bug, cfg: arm_cascade(bug, [cfg["cheap"], cfg["strong"]]),
}


def table(results: dict, bugs: list[str], arms: list[str]) -> str:
    lines = ["| bug | size | " + " | ".join(arms) + " |", "|---|---|" + "---|" * len(arms)]
    tot = {a: dict(cost=0.0, passed=0, n=0) for a in arms}
    for b in bugs:
        row = [b, BUGS[b]["size"]]
        for a in arms:
            r = results.get(b, {}).get(a)
            if not r:
                row.append("—")
                continue
            tier = f" ({r['final_tier'].split('-')[1]})" if r.get("final_tier") else ""
            row.append(f"{'PASS' if r['passed'] else 'FAIL'} ${r['cost']:.3f}{tier}")
            tot[a]["cost"] += r["cost"]; tot[a]["passed"] += r["passed"]; tot[a]["n"] += 1
        lines.append("| " + " | ".join(row) + " |")
    lines.append("| **total** | | " + " | ".join(
        f"**{tot[a]['passed']}/{tot[a]['n']} pass, ${tot[a]['cost']:.3f}**" if tot[a]["n"] else "—" for a in arms) + " |")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bugs", default=",".join(BUGS))
    ap.add_argument("--arms", default=",".join(ARMS))
    ap.add_argument("--cheap", default="haiku")
    ap.add_argument("--strong", default="sonnet")
    ap.add_argument("--redo", action="store_true", help="rerun even if a result exists")
    a = ap.parse_args()
    cfg = dict(cheap=a.cheap, strong=a.strong)
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "runs").mkdir(exist_ok=True)
    rpath = RESULTS / "results.json"
    results = json.loads(rpath.read_text()) if rpath.exists() else {}
    bugs, arms = a.bugs.split(","), a.arms.split(",")
    for bug in bugs:
        for arm in arms:
            if not a.redo and results.get(bug, {}).get(arm):
                continue
            print(f"\n=== {bug} / {arm} ===", flush=True)
            t0 = time.time()
            try:
                r = ARMS[arm](bug, cfg)
            except Exception as e:  # keep the bench going; record the failure
                r = dict(passed=False, cost=0.0, tokens=0, turns=0, seconds=time.time() - t0, stages=[], error=repr(e))
            r["wall"] = time.time() - t0
            results.setdefault(bug, {})[arm] = r
            rpath.write_text(json.dumps(results, indent=1), encoding="utf-8")
            (RESULTS / "runs" / f"{bug}.{arm}.json").write_text(json.dumps(r, indent=1), encoding="utf-8")
            print(f"    -> {'PASS' if r['passed'] else 'FAIL'} ${r['cost']:.4f} {r['tokens']} tok {r['wall']:.0f}s"
                  + (f"  ERROR {r['error']}" if r.get("error") else ""), flush=True)
    md = table(results, bugs, arms)
    print("\n" + md)
    (RESULTS / "table.md").write_text(md, encoding="utf-8")
    readme = ROOT.parent / "README.md"
    if readme.exists():
        import re
        text = readme.read_text(encoding="utf-8")
        block = f"<!-- RESULTS_TABLE -->\n{md}\n<!-- /RESULTS_TABLE -->"
        new = re.sub(r"<!-- RESULTS_TABLE -->.*?(<!-- /RESULTS_TABLE -->|\n\n)", block + "\n\n", text, count=1, flags=re.S)
        readme.write_text(new, encoding="utf-8")


if __name__ == "__main__":
    for s in (sys.stdout, sys.stderr):
        s.reconfigure(encoding="utf-8", errors="replace")
    main()
