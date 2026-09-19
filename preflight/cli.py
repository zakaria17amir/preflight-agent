from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .log import say


def _issue(arg: str) -> str:
    return Path(arg).read_text(encoding="utf-8") if Path(arg).is_file() else arg


def _target(a):
    """(repo path, issue text, display name) from local paths or GitHub repo/issue URLs."""
    from .github import resolve
    root, issue, name = resolve(a.repo, a.issue)
    a.repo, a.issue, a.name = str(root), issue, name
    return root, issue


def cmd_brief(a):
    from .brief import make_brief
    root, issue = _target(a)
    text, res, _ = make_brief(root, issue, model=a.model)
    Path(a.out).write_text(text, encoding="utf-8")
    say(f"wrote {a.out}")


def cmd_scan(a):
    from .scan import render, scan
    root, issue = _target(a)
    print(render(scan(root, issue)))


def cmd_run(a):
    from .run import attempt
    root, issue = _target(a)
    r = attempt(root, issue, brief=Path(a.brief).read_text(encoding="utf-8") if a.brief else None,
                model=a.model, test_cmd=a.test_cmd, max_turns=a.max_turns)
    print(r.summary())
    print(f"scratch copy kept at: {r.workdir}")
    _write_patch(r.diff if r.passed else "", a.repo)


def cmd_handoff(a):
    from .handoff import make_handoff
    from .scan import render, scan
    scan_text = render(scan(Path(a.repo), _issue(a.issue)), max_tree=60) if a.repo else "(not provided)"
    text, res = make_handoff(_issue(a.issue), Path(a.brief).read_text(encoding="utf-8"),
                             Path(a.log).read_text(encoding="utf-8"), model=a.model, scan_text=scan_text)
    Path(a.out).write_text(text, encoding="utf-8")
    say(f"wrote {a.out}")


def cmd_cascade(a):
    from .cascade import cascade
    from .llm import engine
    from .progress import Progress
    root, issue = _target(a)
    tiers = a.tiers.split(",")
    prog = Progress(title=a.name, repo=a.name, issue=issue, engine=engine(), tiers=tiers)
    r = cascade(root, issue, tiers=tiers, test_cmd=a.test_cmd, use_brief=not a.no_brief,
                use_handoff=not a.no_handoff, cheap_max_turns=a.cheap_max_turns, progress=prog)
    if r.brief:
        Path("BRIEF.md").write_text(r.brief, encoding="utf-8")
    if r.handoff:
        Path("BRIEF.v2.md").write_text(r.handoff, encoding="utf-8")
    _record_live(a, r)
    print()
    print(r.summary())
    if r.attempts:
        print(f"final scratch copy: {r.attempts[-1].workdir}")
        _write_patch(r.attempts[-1].diff if r.passed else "", a.repo)


def _write_patch(diff: str, repo: str) -> None:
    """Write the passing diff to PATCH.diff so it can be applied to the real repo."""
    if not diff.strip():
        return
    Path("PATCH.diff").write_text(diff, encoding="utf-8")
    print(f"patch written to PATCH.diff — apply with:  git -C \"{repo}\" apply \"{Path('PATCH.diff').resolve()}\"")


def _record_live(a, r) -> None:
    """Append this cascade run to bench/results/live.json so the dashboard shows it."""
    import json
    import time
    path = Path(__file__).resolve().parents[1] / "bench" / "results" / "live.json"
    try:
        runs = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    except (OSError, ValueError):
        runs = []
    from .llm import engine
    runs.append(dict(
        when=time.strftime("%Y-%m-%d %H:%M:%S"), engine=engine(), repo=a.name, issue=a.issue.strip(),
        tiers=a.tiers.split(","), cheap_max_turns=a.cheap_max_turns, passed=r.passed, cost=r.cost_usd,
        tokens=r.tokens, final_tier=r.final_tier, turns=sum(x.turns for x in r.attempts),
        seconds=sum(s.seconds for s in r.stages),
        stages=[dict(name=s.name, model=s.model, cost=s.cost_usd, tokens=s.tokens, passed=s.passed) for s in r.stages],
        brief=r.brief, handoff=r.handoff, summary=r.attempts[-1].agent_summary[:600] if r.attempts else "",
    ))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(runs, indent=1), encoding="utf-8")
    say(f"recorded to {path.relative_to(Path.cwd()) if path.is_relative_to(Path.cwd()) else path} (dashboard: python bench/dashboard.py)")


def cmd_demo(a):
    """Seed one of the bench bugs into a scratch copy of calcx and print the issue + suggested commands."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bench"))
    from bugs import BUGS, apply_bug
    from .run import fresh_copy
    target = Path(__file__).resolve().parents[1] / "bench" / "target"
    if a.bug not in BUGS:
        sys.exit(f"unknown bug {a.bug!r}; choose from: {', '.join(BUGS)}")
    wd = fresh_copy(target)
    issue = apply_bug(wd, a.bug)
    import subprocess
    subprocess.run(["git", "add", "-A"], cwd=wd, check=True)
    subprocess.run(["git", "-c", "user.email=p@f", "-c", "user.name=preflight", "commit", "-qm", "seed bug"], cwd=wd, check=True)
    Path("ISSUE.md").write_text(issue, encoding="utf-8")
    print(f"Seeded bug '{a.bug}' (size {BUGS[a.bug]['size']}) into:\n  {wd}\n\nIssue (also written to ISSUE.md):\n  {issue}\n")
    print("Now try:")
    print(f'  python -m preflight scan    "{wd}" ISSUE.md')
    print(f'  python -m preflight brief   "{wd}" ISSUE.md')
    print(f'  python -m preflight cascade "{wd}" ISSUE.md --tiers haiku,sonnet --cheap-max-turns 3')
    print(f'  python -m preflight --engine devin cascade "{wd}" ISSUE.md --tiers gpt-5.6-luna,sonnet   # cross-provider')


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(prog="preflight", description="Brief the agent, size the job, start cheap.")
    p.add_argument("--engine", choices=("claude", "devin"), default=None,
                   help="agent CLI to drive: claude (exact $) or devin (48 model families, $ estimated from list prices). "
                        "Default: $PREFLIGHT_ENGINE or claude")
    sub = p.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("brief", help="write BRIEF.md for a repo + issue")
    b.add_argument("repo", help="local path, GitHub repo URL, or GitHub issue URL")
    b.add_argument("issue", nargs="?", help="issue text, a file, a GitHub issue URL, or #N")
    b.add_argument("--model", default="haiku"); b.add_argument("-o", "--out", default="BRIEF.md")
    b.set_defaults(fn=cmd_brief)

    s = sub.add_parser("scan", help="show the zero-token repo scan the brief is built from")
    s.add_argument("repo"); s.add_argument("issue", nargs="?"); s.set_defaults(fn=cmd_scan)

    r = sub.add_parser("run", help="one agent attempt, verified by tests (works on a temp copy)")
    r.add_argument("repo"); r.add_argument("issue", nargs="?"); r.add_argument("--brief"); r.add_argument("--model", default="haiku")
    r.add_argument("--test-cmd", default=None); r.add_argument("--max-turns", type=int, default=None)
    r.set_defaults(fn=cmd_run)

    h = sub.add_parser("handoff", help="distill a failed attempt log into an enriched brief")
    h.add_argument("issue"); h.add_argument("brief"); h.add_argument("log"); h.add_argument("--model", default="haiku")
    h.add_argument("--repo", default=None, help="repo path, to ground the handoff with the zero-token scan")
    h.add_argument("-o", "--out", default="BRIEF.v2.md"); h.set_defaults(fn=cmd_handoff)

    c = sub.add_parser("cascade", help="cheap tier first, escalate with handoff on failure")
    c.add_argument("repo", help="local path, GitHub repo URL, or GitHub issue URL")
    c.add_argument("issue", nargs="?", help="issue text, a file, a GitHub issue URL, or #N"); c.add_argument("--tiers", default="haiku,sonnet")
    c.add_argument("--test-cmd", default=None); c.add_argument("--no-brief", action="store_true")
    c.add_argument("--no-handoff", action="store_true")
    c.add_argument("--cheap-max-turns", type=int, default=None, help="turn budget for every tier except the last")
    c.set_defaults(fn=cmd_cascade)

    d = sub.add_parser("demo", help="seed a bench bug into a scratch copy of calcx for a live demo")
    d.add_argument("bug", nargs="?", default="power_assoc"); d.set_defaults(fn=cmd_demo)

    a = p.parse_args(argv)
    if a.engine:
        import os
        os.environ["PREFLIGHT_ENGINE"] = a.engine
    a.fn(a)


if __name__ == "__main__":
    main()
