"""Recursive-descent parser producing a small AST of tuples.

AST node shapes:
  ("num", float)
  ("var", name)
  ("neg", node)
  ("bin", op, left, right)
  ("call", name, [args])
"""
from __future__ import annotations

from .tokenizer import Token

PRECEDENCE = {"+": 1, "-": 1, "*": 2, "/": 2, "%": 2, "^": 3, "**": 3}
RIGHT_ASSOC = {"^", "**"}


class ParseError(ValueError):
    pass


class _Parser:
    def __init__(self, tokens: list[Token]):
        self.toks = tokens
        self.i = 0

    def peek(self) -> Token | None:
        return self.toks[self.i] if self.i < len(self.toks) else None

    def take(self) -> Token:
        t = self.peek()
        if t is None:
            raise ParseError("unexpected end of input")
        self.i += 1
        return t

    def expect_op(self, value: str) -> None:
        t = self.take()
        if t.kind != "op" or t.value != value:
            raise ParseError(f"expected {value!r} at {t.pos}, got {t.value!r}")

    def parse_expr(self, min_prec: int = 1):
        left = self.parse_unary()
        while True:
            t = self.peek()
            if t is None or t.kind != "op" or t.value not in PRECEDENCE:
                return left
            prec = PRECEDENCE[t.value]
            if prec < min_prec:
                return left
            self.take()
            next_min = prec if t.value in RIGHT_ASSOC else prec + 1
            right = self.parse_expr(next_min)
            left = ("bin", t.value, left, right)

    def parse_unary(self):
        t = self.peek()
        if t is not None and t.kind == "op" and t.value == "-":
            self.take()
            return ("neg", self.parse_unary())
        if t is not None and t.kind == "op" and t.value == "+":
            self.take()
            return self.parse_unary()
        return self.parse_primary()

    def parse_primary(self):
        t = self.take()
        if t.kind == "num":
            return ("num", float(t.value))
        if t.kind == "name":
            nxt = self.peek()
            if nxt is not None and nxt.kind == "op" and nxt.value == "(":
                self.take()
                args = []
                if not (self.peek() and self.peek().kind == "op" and self.peek().value == ")"):
                    args.append(self.parse_expr())
                    while self.peek() and self.peek().kind == "op" and self.peek().value == ",":
                        self.take()
                        args.append(self.parse_expr())
                self.expect_op(")")
                return ("call", t.value, args)
            return ("var", t.value)
        if t.kind == "op" and t.value == "(":
            node = self.parse_expr()
            self.expect_op(")")
            return node
        raise ParseError(f"unexpected token {t.value!r} at {t.pos}")


def parse(tokens: list[Token]):
    p = _Parser(tokens)
    node = p.parse_expr()
    if p.peek() is not None:
        raise ParseError(f"trailing input at {p.peek().pos}")
    return node
