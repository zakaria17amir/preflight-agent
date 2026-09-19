from __future__ import annotations

import math

from .units import Quantity, convert


class EvalError(ValueError):
    pass


FUNCS = {
    "sqrt": math.sqrt,
    "abs": abs,
    "min": min,
    "max": max,
    "round": lambda x, n=0: round(x, int(n)),
    "avg": lambda *xs: sum(xs) / len(xs),
    "log": lambda x, base=math.e: math.log(x, base),
}


def _binop(op: str, a: float, b: float) -> float:
    if op == "+":
        return a + b
    if op == "-":
        return a - b
    if op == "*":
        return a * b
    if op == "/":
        if b == 0:
            raise EvalError("division by zero")
        return a / b
    if op == "%":
        if b == 0:
            raise EvalError("modulo by zero")
        return math.fmod(a, b)
    if op in ("^", "**"):
        return a ** b
    raise EvalError(f"unknown operator {op!r}")


def evaluate(node, env: dict) -> float:
    kind = node[0]
    if kind == "num":
        return node[1]
    if kind == "var":
        name = node[1]
        if name not in env:
            raise EvalError(f"unknown variable {name!r}")
        return float(env[name])
    if kind == "neg":
        return -evaluate(node[1], env)
    if kind == "bin":
        _, op, l, r = node
        return _binop(op, evaluate(l, env), evaluate(r, env))
    if kind == "call":
        _, name, args = node
        if name == "to":
            # to(value, from_unit, to_unit) — unit names are passed as variables holding strings
            if len(args) != 3:
                raise EvalError("to() takes 3 arguments")
            value = evaluate(args[0], env)
            src = env.get(args[1][1]) if args[1][0] == "var" else None
            dst = env.get(args[2][1]) if args[2][0] == "var" else None
            if not isinstance(src, str) or not isinstance(dst, str):
                raise EvalError("to() unit arguments must be unit names")
            return convert(Quantity(value, src), dst).value
        if name not in FUNCS:
            raise EvalError(f"unknown function {name!r}")
        vals = [evaluate(a, env) for a in args]
        try:
            return float(FUNCS[name](*vals))
        except TypeError as e:
            raise EvalError(f"bad arguments to {name}(): {e}") from e
    raise EvalError(f"bad node {node!r}")
