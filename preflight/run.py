"""One agent attempt: copy the repo to a scratch dir, let the agent work, verify with the repo's tests."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import llm
from .scan import scan

ATTEMPT_SYSTEM = (
    "You are a coding agent fixing a bug in the repository in the current working directory. "
    "Make the smallest correct change. Run the tests to verify. Do not modify or delete tests. "
    "When done, reply with a 3-line summary: files changed, what the root cause was, test status."
)

ATTEMPT_PROMPT_COLD = """# Issue
{issue}

Fix this issue in the repository in the current directory."""

ATTEMPT_PROMPT_BRIEFED = """# Issue
{issue}

# Brief from the tech lead (read this before touching anything)
{brief}

Fix this issue in the repository in the current directory."""


@dataclass
class TestResult:
    passed: bool
    summary: str
    output: str = field(repr=False, default="")


@dataclass
class Attempt:
    model: str
    passed: bool
    cost_usd: float
    tokens: int
    turns: int
    seconds: float
    tests: TestResult
    agent_summary: str
    diff: str = field(repr=False, default="")
    workdir: Path | None = None

    def summary(self) -> str:
        return (f"[{self.model}] {'PASS' if self.passed else 'FAIL'} ${self.cost_usd:.4f} {self.tokens} tok "
                f"{self.turns} turns {self.seconds:.0f}s | {self.tests.summary}")

    def transcript_for_handoff(self) -> str:
        return (f"model: {self.model}\nresult: {'PASS' if self.passed else 'FAIL'}\n\n"
                f"## Agent's own summary\n{self.agent_summary}\n\n## Diff produced\n{self.diff[:6000] or '(no changes)'}\n\n"
                f"## Test output\n{self.tests.output[-4000:]}")


def run_tests(root: Path, test_cmd: str, timeout: int = 300) -> TestResult:
    try:
        p = subprocess.run(test_cmd, shell=True, cwd=str(root), capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return TestResult(False, "tests timed out", "")
    out = (p.stdout + "\n" + p.stderr).strip()
    last = next((l for l in reversed(out.splitlines()) if l.strip()), "")
    return TestResult(p.returncode == 0, last[:200], out)


def fresh_copy(root: Path) -> Path:
    dst = Path(tempfile.mkdtemp(prefix="preflight_")) / root.name
    shutil.copytree(root, dst, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache", ".preflight"))
    subprocess.run(["git", "init", "-q"], cwd=dst, check=True)
    subprocess.run(["git", "config", "core.autocrlf", "false"], cwd=dst, check=True)
    subprocess.run(["git", "add", "-A"], cwd=dst, check=True)
    subprocess.run(["git", "-c", "user.email=p@f", "-c", "user.name=preflight", "commit", "-qm", "base"], cwd=dst, check=True)
    return dst


def git_diff(root: Path) -> str:
    return subprocess.run(["git", "diff"], cwd=root, capture_output=True, text=True, encoding="utf-8",
                          errors="replace").stdout


def attempt(root: Path, issue: str, brief: str | None = None, model: str = "haiku", test_cmd: str | None = None,
            workdir: Path | None = None, timeout: int = 900) -> Attempt:
    """Run one attempt. If `workdir` is given, work there (already a fresh copy); else make one."""
    wd = workdir or fresh_copy(root)
    test_cmd = test_cmd or scan(root, issue).test_cmd
    prompt = (ATTEMPT_PROMPT_BRIEFED.format(issue=issue, brief=brief) if brief
              else ATTEMPT_PROMPT_COLD.format(issue=issue))
    t0 = time.time()
    try:
        res = llm.call(prompt, model=model, cwd=wd, agentic=True, timeout=timeout, system=ATTEMPT_SYSTEM)
        text, cost, tok, turns = res.text, res.cost_usd, res.total_tokens, res.num_turns
    except subprocess.TimeoutExpired:
        text, cost, tok, turns = "(agent timed out)", 0.0, 0, 0
    secs = time.time() - t0
    tests = run_tests(wd, test_cmd)
    return Attempt(model=model, passed=tests.passed, cost_usd=cost, tokens=tok, turns=turns, seconds=secs,
                   tests=tests, agent_summary=text, diff=git_diff(wd), workdir=wd)
