"""Progress output to stderr so long-running stages are visible. Set PREFLIGHT_QUIET=1 to silence."""

from __future__ import annotations

import os
import sys
import time

_T0 = time.time()
QUIET = os.environ.get("PREFLIGHT_QUIET") == "1"


def say(msg: str) -> None:
    if QUIET:
        return
    print(f"  [preflight +{time.time() - _T0:5.1f}s] {msg}", file=sys.stderr, flush=True)


def block(title: str, body: str, max_lines: int = 60) -> None:
    """Print a titled block of text (a brief, a handoff, a diff) to stderr."""
    if QUIET:
        return
    lines = body.rstrip().splitlines()
    more = f"\n  ... ({len(lines) - max_lines} more lines)" if len(lines) > max_lines else ""
    bar = "─" * max(8, min(72, len(title) + 4))
    print(f"\n  ┌{bar}\n  │ {title}\n  └{bar}", file=sys.stderr)
    print("\n".join("  " + line for line in lines[:max_lines]) + more + "\n", file=sys.stderr, flush=True)
