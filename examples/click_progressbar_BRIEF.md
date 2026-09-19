<!-- preflight brief | model=claude-haiku-4-5-20251001 | cost=$0.0182 | tokens=10914 | size=M tier=mid | heuristic_size=M -->
# Brief

## Start here
1. `src/click/_termui_impl.py` — ProgressBar class with iteration and completion logic
2. `src/click/termui.py` — progressbar() function wrapping the class, generator handling
3. `tests/test_termui.py` — existing progressbar tests; search for length-related test cases
4. `src/click/testing.py` — CliRunner and output capture (used by test harness)

## Conventions
- Type hints required; match existing patterns with `t.Generic`, `cabc.Generator`, etc.
- Pre-commit hooks active (black, isort, etc.); run `pytest` to verify
- Tests in `tests/test_termui.py`; use CliRunner fixture from conftest
- Context manager protocol (`__enter__`/`__exit__`) must be preserved

## Verify
```bash
pytest tests/test_termui.py -k progressbar -v
```
Proof: test that passes `length=100` to progressbar with generator yielding 70 items; assert bar displays 100% when loop exits naturally.

## Risks
- Don't change `update(n)` signature (existing code calls it explicitly for manual progress)
- Generator length may be None—handle gracefully, don't assume declared length is always set
- TTY vs. non-TTY modes must behave identically (no silent-mode regressions)
- Avoid breaking stream capture in tests (CliRunner uses it for assertions)

## Size
**M** — ProgressBar logic touches both `_termui_impl.py` (state/iteration) and `termui.py` (generator integration), plus test addition.

## Tier
**mid** — straightforward state-machine fix in iterator protocol, but needs careful edge-case testing (None length, zero items, etc.) across platforms.
