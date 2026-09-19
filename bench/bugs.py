"""Seeded bugs for the calcx target. Each bug = a mutation of the clean tree + an issue written like a human would.

Issues intentionally do NOT name files: that's the orientation problem the brief is meant to solve.
"""
from __future__ import annotations

from pathlib import Path


def _sub(root: Path, rel: str, old: str, new: str) -> None:
    p = root / rel
    text = p.read_text(encoding="utf-8")
    assert old in text, f"{rel}: pattern not found: {old!r}"
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


BUGS = {
    # S: one-line off-by-one in the report's ok counter message
    "report_counter": dict(
        size="S",
        issue="The summary line at the bottom of the results table says e.g. `3/3 ok` even when one of the rows is an "
              "error. Looks like errors are being counted as ok.",
        apply=lambda r: _sub(r, "calcx/report.py", 'if not r.startswith("error:")', 'if not r.startswith("Error:")'),
    ),
    # S: temperature conversion wrong direction for Fahrenheit
    "fahrenheit": dict(
        size="S",
        issue="Converting 100 C to F gives the wrong answer (I get something around 149 instead of 212). Celsius to "
              "Kelvin seems fine, so it's specifically Fahrenheit.",
        apply=lambda r: _sub(r, "calcx/units.py", "(x - 273.15) * 9 / 5 + 32", "(x - 273.15) * 5 / 9 + 32"),
    ),
    # M: power operator became left-associative (parser precedence logic)
    "power_assoc": dict(
        size="M",
        issue="`2 ^ 3 ^ 2` evaluates to 64 but it should be 512 (exponentiation is right-associative, like Python). "
              "`2 ** 3 ** 2` has the same problem. Everything else about precedence looks right.",
        apply=lambda r: _sub(r, "calcx/parser.py", "next_min = prec if t.value in RIGHT_ASSOC else prec + 1",
                             "next_min = prec + 1"),
    ),
    # M: tokenizer drops the leading-dot number form, and the error surfaces as a ParseError far from the cause
    "leading_dot": dict(
        size="M",
        issue="Expressions like `.5 * 2` blow up with a confusing error about an unexpected character. Numbers with "
              "a leading dot used to work (they're valid in Python). Numbers like `2.` still work.",
        apply=lambda r: _sub(r, "calcx/tokenizer.py", r"(\d+\.\d*|\d*\.\d+|\d+)", r"(\d+\.\d*|\d+)"),
    ),
    # L: cross-module: the to() unit conversion returns the base-unit value instead of the target-unit value,
    # AND evaluate_batch swallows UnitError into a generic ValueError message that hides it. Two files, one symptom.
    "unit_to_base": dict(
        size="L",
        issue="`to(2.5, km, m)` returns 2500 correctly, but `to(2500, m, km)` returns 2500 instead of 2.5, and "
              "`to(1, mi, km)` gives 1609.344. It looks like conversions only work when the target is the base unit. "
              "Also, when I put a bad unit in a batch report I get `error: cannot convert` instead of the unit error "
              "type I'd expect to be able to match on; please make sure UnitError is preserved for batch rows too.",
        apply=lambda r: (
            _sub(r, "calcx/units.py", "return Quantity(from_base(to_base(q), unit), unit)",
                 "return Quantity(to_base(q), unit)"),
            _sub(r, "calcx/report.py", "except (TokenizeError, ParseError, EvalError, ValueError) as err:\n"
                 "            rows.append((e, f\"error: {err}\"))",
                 "except (TokenizeError, ParseError, EvalError) as err:\n"
                 "            rows.append((e, f\"error: {err}\"))\n"
                 "        except ValueError as err:\n"
                 "            rows.append((e, \"error: cannot convert\"))"),
        ),
    ),
}


def apply_bug(root: Path, name: str) -> str:
    BUGS[name]["apply"](root)
    return BUGS[name]["issue"]
