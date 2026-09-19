from __future__ import annotations

import argparse
import sys
from pathlib import Path


def cmd_brief(a):
    from .brief import make_brief
    issue = Path(a.issue).read_text() if Path(a.issue).is_file() else a.issue
    text, res, _ = make_brief(Path(a.repo), issue, model=a.model)
    Path(a.out).write_text(text, encoding="utf-8")
    print(text)
    print(f"\n[brief] {res.model} ${res.cost_usd:.4f} {res.total_tokens} tok {res.duration_ms/1000:.1f}s -> {a.out}", file=sys.stderr)


def cmd_scan(a):
    from .scan import render, scan
    issue = Path(a.issue).read_text() if Path(a.issue).is_file() else a.issue
    print(render(scan(Path(a.repo), issue)))


def cmd_run(a):
    from .run import attempt
    r = attempt(Path(a.repo), a.issue, brief=Path(a.brief).read_text() if a.brief else None,
                model=a.model, test_cmd=a.test_cmd)
    print(r.summary())


def cmd_handoff(a):
    from .handoff import make_handoff
    text, res = make_handoff(a.issue, Path(a.brief).read_text(), Path(a.log).read_text(), model=a.model)
    Path(a.out).write_text(text, encoding="utf-8")
    print(text)
    print(f"\n[handoff] {res.model} ${res.cost_usd:.4f} -> {a.out}", file=sys.stderr)


def cmd_cascade(a):
    from .cascade import cascade
    r = cascade(Path(a.repo), a.issue, tiers=a.tiers.split(","), test_cmd=a.test_cmd, use_brief=not a.no_brief,
                use_handoff=not a.no_handoff, cheap_max_turns=a.cheap_max_turns)
    print(r.summary())


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(prog="preflight", description="Brief the agent, size the job, start cheap.")
    sub = p.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("brief", help="write BRIEF.md for a repo + issue")
    b.add_argument("repo"); b.add_argument("issue", help="issue text or path to a file")
    b.add_argument("--model", default="haiku"); b.add_argument("-o", "--out", default="BRIEF.md")
    b.set_defaults(fn=cmd_brief)

    s = sub.add_parser("scan", help="show the zero-token repo scan the brief is built from")
    s.add_argument("repo"); s.add_argument("issue"); s.set_defaults(fn=cmd_scan)

    r = sub.add_parser("run", help="one agent attempt, verified by tests (works on a temp copy)")
    r.add_argument("repo"); r.add_argument("issue"); r.add_argument("--brief"); r.add_argument("--model", default="haiku")
    r.add_argument("--test-cmd", default=None); r.set_defaults(fn=cmd_run)

    h = sub.add_parser("handoff", help="distill a failed attempt log into an enriched brief")
    h.add_argument("issue"); h.add_argument("brief"); h.add_argument("log"); h.add_argument("--model", default="haiku")
    h.add_argument("-o", "--out", default="BRIEF.v2.md"); h.set_defaults(fn=cmd_handoff)

    c = sub.add_parser("cascade", help="cheap tier first, escalate with handoff on failure")
    c.add_argument("repo"); c.add_argument("issue"); c.add_argument("--tiers", default="haiku,sonnet")
    c.add_argument("--test-cmd", default=None); c.add_argument("--no-brief", action="store_true")
    c.add_argument("--no-handoff", action="store_true")
    c.add_argument("--cheap-max-turns", type=int, default=None, help="turn budget for every tier except the last")
    c.set_defaults(fn=cmd_cascade)

    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
