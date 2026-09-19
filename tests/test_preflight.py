"""Tests for the zero-token parts of preflight, and a guard that every seeded bug really breaks the target."""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "bench"))

from bugs import BUGS, apply_bug  # noqa: E402
from preflight.brief import heuristic_size, parse_size_tier  # noqa: E402
from preflight.scan import keywords, render, scan  # noqa: E402

TARGET = ROOT / "bench" / "target"


def test_keywords_drop_stopwords_and_split_identifiers():
    kws = keywords("The evaluate_batch function returns the wrong ok count when a row is an error")
    assert "evaluate_batch" in kws and "evaluate" in kws and "batch" in kws
    assert "the" not in [k.lower() for k in kws]


def test_scan_ranks_the_right_file_for_each_bug():
    expected = {"report_counter": "calcx/report.py", "fahrenheit": "calcx/units.py", "power_assoc": "calcx/parser.py",
                "leading_dot": "calcx/tokenizer.py", "unit_to_base": "calcx/units.py"}
    for bug, want in expected.items():
        s = scan(TARGET, BUGS[bug]["issue"])
        top3 = [h.path for h in s.hits[:3]]
        assert want in top3, f"{bug}: expected {want} in top-3, got {top3}"


def test_scan_detects_test_command_and_renders():
    s = scan(TARGET, "anything")
    assert s.test_cmd.startswith("pytest")
    out = render(s)
    assert "# File tree:" in out and "calcx/parser.py" in out


def test_heuristic_size_is_a_letter():
    assert heuristic_size(scan(TARGET, BUGS["fahrenheit"]["issue"])) in {"S", "M", "L"}


def test_parse_size_tier():
    text = "## Start here\n- x\n\n## Size\n**M** - two files\n\n## Tier\nRecommended: mid, because...\n"
    assert parse_size_tier(text) == ("M", "mid")
    assert parse_size_tier("nothing here") == ("?", "?")


@pytest.mark.parametrize("bug", list(BUGS))
def test_each_seeded_bug_breaks_the_target(tmp_path, bug):
    wd = tmp_path / "t"
    shutil.copytree(TARGET, wd, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    apply_bug(wd, bug)
    p = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x"], cwd=wd, capture_output=True, text=True)
    assert p.returncode != 0, f"{bug} did not make any test fail:\n{p.stdout}"


def test_clean_target_is_green():
    p = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=TARGET, capture_output=True, text=True)
    assert p.returncode == 0, p.stdout
