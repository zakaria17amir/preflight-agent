from __future__ import annotations

import re
from dataclasses import dataclass

TOKEN_RE = re.compile(r"\s*(?:(\d+\.\d*|\d*\.\d+|\d+)|([A-Za-z_][A-Za-z0-9_]*)|(\*\*|[-+*/%^(),]))")


@dataclass(frozen=True)
class Token:
    kind: str  # "num" | "name" | "op"
    value: str
    pos: int


class TokenizeError(ValueError):
    pass


def tokenize(src: str) -> list[Token]:
    """Split an expression into tokens. Whitespace is insignificant."""
    out: list[Token] = []
    pos = 0
    while pos < len(src):
        m = TOKEN_RE.match(src, pos)
        if not m or m.end() == pos:
            if src[pos:].strip() == "":
                break
            raise TokenizeError(f"unexpected character {src[pos]!r} at {pos}")
        num, name, op = m.groups()
        if num is not None:
            out.append(Token("num", num, m.start(1)))
        elif name is not None:
            out.append(Token("name", name, m.start(2)))
        else:
            out.append(Token("op", op, m.start(3)))
        pos = m.end()
    return out
