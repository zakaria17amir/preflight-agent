"""Deterministic, zero-token repo scan. Everything the LLM sees about the repo comes from here."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

IGNORE_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".mypy_cache",
               ".pytest_cache", ".idea", ".vscode", "target", ".tox", ".preflight"}
CODE_EXT = {".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java", ".rb", ".cs", ".php", ".kt", ".swift", ".c", ".cpp", ".h"}
MAX_FILE_BYTES = 200_000
STOPWORDS = {"the", "a", "an", "and", "or", "of", "to", "in", "is", "it", "that", "this", "when", "with", "for",
             "on", "be", "not", "should", "but", "are", "as", "at", "by", "from", "if", "we", "i", "you", "does",
             "doesn", "t", "s", "returns", "return", "error", "bug", "fix", "instead", "gets", "get", "wrong"}

TEST_HINTS = [
    ("pyproject.toml", "pytest"), ("pytest.ini", "pytest"), ("setup.cfg", "pytest"), ("tox.ini", "pytest"),
    ("package.json", "npm test"), ("Cargo.toml", "cargo test"), ("go.mod", "go test ./..."),
    ("pom.xml", "mvn test"), ("build.gradle", "gradle test"), ("Gemfile", "bundle exec rspec"),
]


@dataclass
class FileHit:
    path: str
    score: float
    lines: list[str] = field(default_factory=list)


@dataclass
class Scan:
    root: Path
    tree: list[str]
    readme: str
    test_cmd: str
    conventions: list[str]
    hits: list[FileHit]
    n_files: int
    languages: dict[str, int]

    def keywords_hit_modules(self) -> int:
        return len({Path(h.path).parts[0] for h in self.hits[:8]}) if self.hits else 0


def _walk(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in IGNORE_DIRS and not d.startswith("."))
        for f in sorted(filenames):
            yield Path(dirpath) / f


def keywords(issue: str) -> list[str]:
    toks = re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", issue)
    seen, out = set(), []
    for t in toks:
        tl = t.lower()
        if tl in STOPWORDS or tl in seen:
            continue
        seen.add(tl)
        out.append(t)
        # split camelCase / snake_case into parts too
        for p in re.split(r"_|(?<=[a-z])(?=[A-Z])", t):
            pl = p.lower()
            if len(pl) > 2 and pl not in STOPWORDS and pl not in seen:
                seen.add(pl)
                out.append(p)
    return out[:40]


def detect_test_cmd(root: Path, tree: list[str]) -> str:
    names = {Path(p).name for p in tree}
    if "package.json" in names:
        return "npm test"
    for fname, cmd in TEST_HINTS:
        if fname in names:
            return cmd
    if any(p.endswith((".py",)) for p in tree):
        return "pytest -q"
    return "unknown"


def detect_conventions(root: Path, tree: list[str], sample: list[Path]) -> list[str]:
    conv = []
    names = {Path(p).name for p in tree}
    for marker, note in [("pyproject.toml", "Python project (pyproject.toml)"), ("ruff.toml", "ruff lint config"),
                         (".pre-commit-config.yaml", "pre-commit hooks present"), ("tsconfig.json", "TypeScript"),
                         (".eslintrc.json", "eslint"), ("Makefile", "Makefile present: check targets"),
                         ("CONTRIBUTING.md", "CONTRIBUTING.md exists: read before editing")]:
        if marker in names:
            conv.append(note)
    tests_dirs = sorted({str(Path(p).parent) for p in tree if re.search(r"(^|/)(tests?|__tests__|spec)(/|$)", p)})
    if tests_dirs:
        conv.append(f"tests live in: {', '.join(tests_dirs[:4])}")
    typed = sum(1 for f in sample if f.suffix == ".py" and "->" in f.read_text(errors="ignore")[:20000])
    if sample and typed >= max(1, len(sample) // 2):
        conv.append("Python code uses type hints; keep them")
    return conv


def scan(root: Path, issue: str, max_hits: int = 12) -> Scan:
    root = root.resolve()
    files = [p for p in _walk(root) if p.is_file()]
    tree = [p.relative_to(root).as_posix() for p in files]
    langs: dict[str, int] = {}
    for p in files:
        if p.suffix in CODE_EXT:
            langs[p.suffix] = langs.get(p.suffix, 0) + 1
    readme = ""
    for cand in ("README.md", "README.rst", "README.txt", "README"):
        if (root / cand).exists():
            readme = (root / cand).read_text(errors="ignore")[:4000]
            break
    kws = keywords(issue)
    hits: list[FileHit] = []
    code_files = [p for p in files if p.suffix in CODE_EXT and p.stat().st_size < MAX_FILE_BYTES]
    for p in code_files:
        text = p.read_text(errors="ignore")
        low = text.lower()
        rel = p.relative_to(root).as_posix()
        score = 0.0
        matched_lines: list[str] = []
        for kw in kws:
            c = low.count(kw.lower())
            if c:
                score += (1 + min(c, 5)) * (2.0 if kw.lower() in rel.lower() else 1.0)
        if score:
            is_test = bool(re.search(r"(^|/)(tests?|__tests__|spec)(/|$)|test_|_test\.|\.spec\.", rel))
            score *= 0.6 if is_test else 1.0
            for i, line in enumerate(text.splitlines()):
                if any(kw.lower() in line.lower() for kw in kws[:8]) and re.search(r"\b(def|class|function|fn|func|export)\b", line):
                    matched_lines.append(f"L{i+1}: {line.strip()[:110]}")
                if len(matched_lines) >= 5:
                    break
            hits.append(FileHit(rel, round(score, 1), matched_lines))
    hits.sort(key=lambda h: -h.score)
    sample = [root / h.path for h in hits[:6]] or code_files[:6]
    return Scan(root=root, tree=tree, readme=readme, test_cmd=detect_test_cmd(root, tree),
                conventions=detect_conventions(root, tree, sample), hits=hits[:max_hits],
                n_files=len(files), languages=langs)


def render(s: Scan, max_tree: int = 120) -> str:
    """Compact text view of the scan for the LLM prompt."""
    tree = s.tree if len(s.tree) <= max_tree else s.tree[:max_tree] + [f"... ({len(s.tree) - max_tree} more)"]
    parts = [f"# Repo: {s.root.name} ({s.n_files} files; languages: {s.languages})",
             f"# Detected test command: {s.test_cmd}",
             "# Conventions detected:", *([f"- {c}" for c in s.conventions] or ["- none"]),
             "# File tree:", *tree,
             "# README (truncated):", s.readme or "(none)",
             "# Files matching issue keywords (ranked):"]
    for h in s.hits:
        parts.append(f"- {h.path} (score {h.score})")
        parts += [f"    {l}" for l in h.lines]
    return "\n".join(parts)
