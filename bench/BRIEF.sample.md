<!-- preflight brief | model=claude-haiku-4-5-20251001 | cost=$0.1842 | tokens=89926 | size=S tier=cheap | heuristic_size=S -->
# Brief

## Start here
1. **calcx/units.py** — Temperature conversion logic lives here; bug is in C→F formula.
2. **tests/test_calcx.py** — See existing temperature tests and verify your fix passes them.
3. **calcx/evaluator.py** — Understand how `to()` conversion function is dispatched to the units module.

## Conventions
- Keep type hints (project uses them throughout).
- Test changes in `tests/` following existing test patterns.
- Python 3.x with pyproject.toml; no external deps for core logic.

## Verify
```bash
pytest -q
```
Should pass all tests after fix. Specifically check for any tests converting Celsius→Fahrenheit; if none exist, add one: `to(100, "C", "F")` should equal `212`.

## Risks
- Don't break C→K or K→C conversions (only F is broken).
- Temperature conversion formula is well-defined (C→F = C × 9/5 + 32); a simple arithmetic or operator error is likely.
- Verify the fix handles both integer and float inputs correctly.

## Size
**S** — Likely a single formula or operator typo in the conversion table. Localized to one place in units.py.

## Tier
**cheap** — Straightforward formula bug, no architectural changes needed. Once you locate the broken formula, the fix is a line or two.
