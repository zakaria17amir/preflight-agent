"""Format a batch of expression results as a fixed-width text table."""
from __future__ import annotations

from .evaluator import EvalError, evaluate
from .parser import ParseError, parse
from .tokenizer import TokenizeError, tokenize


def calc(expr: str, env: dict | None = None) -> float:
    return evaluate(parse(tokenize(expr)), env or {})


def evaluate_batch(exprs: list[str], env: dict | None = None) -> list[tuple[str, str]]:
    """Return (expr, result_or_error) pairs. Errors never abort the batch."""
    rows = []
    for e in exprs:
        try:
            rows.append((e, f"{calc(e, env):.4g}"))
        except (TokenizeError, ParseError, EvalError, ValueError) as err:
            rows.append((e, f"error: {err}"))
    return rows


def format_report(rows: list[tuple[str, str]], title: str = "Results") -> str:
    """Two-column table. Columns are sized to the widest cell; header underlined with '-'."""
    if not rows:
        return f"{title}\n(no rows)"
    w_expr = max(len("expr"), *(len(r[0]) for r in rows))
    w_res = max(len("result"), *(len(r[1]) for r in rows))
    lines = [title, f"{'expr'.ljust(w_expr)}  {'result'.rjust(w_res)}", f"{'-' * w_expr}  {'-' * w_res}"]
    for expr, res in rows:
        lines.append(f"{expr.ljust(w_expr)}  {res.rjust(w_res)}")
    ok = sum(1 for _, r in rows if not r.startswith("error:"))
    lines.append(f"{ok}/{len(rows)} ok")
    return "\n".join(lines)
