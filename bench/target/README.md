# calcx

Tiny expression calculator: tokenizer -> recursive-descent parser -> evaluator, with unit conversion and a text report.

```
from calcx import calc
calc("2 ^ 3 ^ 2")            # 512
calc("to(2.5, km, m)", {"km": "km", "m": "m"})
```

Run tests with `pytest -q`.
