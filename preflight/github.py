"""Resolve GitHub URLs to a local clone + issue text, via the `gh` CLI (which owns auth)."""

from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

from .log import say

_GH = re.compile(r"^https?://github\.com/([\w.-]+)/([\w.-]+?)(?:\.git)?(?:/issues/(\d+))?/?$")


def parse(url: str) -> tuple[str, str, int | None] | None:
    m = _GH.match(url.strip())
    return (m.group(1), m.group(2), int(m.group(3)) if m.group(3) else None) if m else None


def clone(owner: str, repo: str) -> Path:
    dst = Path(tempfile.mkdtemp(prefix=f"preflight_gh_{repo}_")) / repo
    say(f"cloning github.com/{owner}/{repo} (shallow) -> {dst}")
    p = subprocess.run(
        ["git", "clone", "-q", "--depth", "1", f"https://github.com/{owner}/{repo}.git", str(dst)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if p.returncode != 0:
        raise RuntimeError(
            f"clone of github.com/{owner}/{repo} failed: {p.stderr.strip().splitlines()[-1] if p.stderr.strip() else 'unknown error'}"
        )
    return dst


def issue_text(owner: str, repo: str, number: int) -> str:
    say(f"fetching issue #{number} from github.com/{owner}/{repo}")
    p = subprocess.run(
        ["gh", "issue", "view", str(number), "-R", f"{owner}/{repo}", "--json", "title,body"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if p.returncode != 0:
        raise RuntimeError(f"gh issue view failed: {p.stderr.strip()[-300:]}")
    import json

    d = json.loads(p.stdout)
    return f"{d['title']}\n\n{d.get('body') or ''}".strip()


def resolve(repo_arg: str, issue_arg: str | None) -> tuple[Path, str, str]:
    """-> (local repo path, issue text, display name).

    repo_arg: local path, GitHub repo URL, or GitHub issue URL.
    issue_arg: issue text, path to a file, GitHub issue URL, '#N' / 'N' (issue number in repo_arg), or None
               when repo_arg itself is an issue URL.
    """
    gh = parse(repo_arg)
    if gh:
        owner, repo, num = gh
        root = clone(owner, repo)
        name = f"{owner}/{repo}"
        if issue_arg is None:
            if num is None:
                raise SystemExit("give an issue: text, a file, an issue URL, or '#N'")
        else:
            gh_issue = parse(issue_arg)
            if gh_issue and gh_issue[2]:
                owner, repo, num = gh_issue
            elif re.fullmatch(r"#?\d+", issue_arg.strip()):
                num = int(issue_arg.strip().lstrip("#"))
            else:
                return root, _local_issue(issue_arg), name
        return root, issue_text(owner, repo, num), f"{name}#{num}"
    root = Path(repo_arg)
    if not root.is_dir():
        raise SystemExit(f"not a directory or GitHub URL: {repo_arg}")
    if issue_arg is None:
        raise SystemExit("give an issue: text, a file, or a GitHub issue URL")
    gh_issue = parse(issue_arg)
    if gh_issue and gh_issue[2]:
        return root, issue_text(*gh_issue), f"{root.name} / {gh_issue[0]}/{gh_issue[1]}#{gh_issue[2]}"
    return root, _local_issue(issue_arg), root.name


def _local_issue(arg: str) -> str:
    return Path(arg).read_text(encoding="utf-8") if Path(arg).is_file() else arg
