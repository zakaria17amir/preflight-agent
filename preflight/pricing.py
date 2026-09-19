"""List-price table for Devin CLI models, parsed from `devin models list`.

Devin CLI does not report dollar cost per call, only tokens (in the ATIF export). We price those tokens at the
list prices the CLI itself prints. Every number derived from this is an ESTIMATE and is labelled as such.
"""
from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path

CACHE = Path(__file__).resolve().parents[1] / "bench" / "results" / "devin_prices.json"
CACHE_TTL_S = 24 * 3600

# "  claude-haiku-4-5-...   Claude Haiku 4.5 Medium  [200K context, $1 / 1M Input · $0.1 / 1M Cached input · $5 / 1M Output]"
_LINE = re.compile(r"^\s{2}(\S+)\s{2,}(.+?)\s+\[[^\]]*?\$([\d.]+) / 1M Input · \$([\d.]+) / 1M Cached input · \$([\d.]+) / 1M Output\]")
_FAMILY = re.compile(r"^(\S.*?) \(([\w.-]+)\)\s*$")
_FREE = re.compile(r"^\s{2}(\S+)\s{2,}(.+?)\s+\[[^\]]*\bFree\b")


def parse(text: str) -> dict:
    """-> {"variants": {display_name: {"uid", "family", "in", "cached", "out"}}, "families": {slug: display}}"""
    variants, families, cur = {}, {}, None
    for line in text.splitlines():
        m = _FAMILY.match(line)
        if m:
            cur = m.group(2)
            families[cur] = m.group(1)
            continue
        m = _LINE.match(line)
        if m:
            uid, name, i, c, o = m.groups()
            variants[name.strip()] = dict(uid=uid, family=cur, **{"in": float(i), "cached": float(c), "out": float(o)})
            continue
        m = _FREE.match(line)
        if m:
            variants[m.group(2).strip()] = dict(uid=m.group(1), family=cur, **{"in": 0.0, "cached": 0.0, "out": 0.0})
    return dict(variants=variants, families=families, fetched=time.time())


def load(env: dict | None = None) -> dict:
    if CACHE.exists():
        try:
            data = json.loads(CACHE.read_text(encoding="utf-8"))
            if time.time() - data.get("fetched", 0) < CACHE_TTL_S and data.get("variants"):
                return data
        except ValueError:
            pass
    p = subprocess.run(["devin", "models", "list"], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=env, timeout=60)
    data = parse(p.stdout)
    if data["variants"]:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(data, indent=1), encoding="utf-8")
    return data


def lookup(model_name: str, table: dict) -> dict | None:
    """Match the ATIF `agent.model_name` (e.g. 'GPT-5.6 Luna Medium Thinking') to a priced variant."""
    v = table.get("variants", {})
    if model_name in v:
        return v[model_name]
    # longest variant display name that is a prefix of the reported name, then the reverse
    best = max((n for n in v if model_name.startswith(n)), key=len, default=None)
    if best is None:
        best = max((n for n in v if n.startswith(model_name)), key=len, default=None)
    if best is None:
        low = model_name.lower()
        best = max((n for n in v if n.lower().split(" ")[0] in low and n.lower().split(" ")[1:2] and n.lower().split(" ")[1] in low),
                   key=len, default=None)
    return v.get(best) if best else None


def estimate(prompt_tokens: int, cached_tokens: int, completion_tokens: int, price: dict | None) -> float | None:
    if not price:
        return None
    fresh = max(0, prompt_tokens - cached_tokens)
    return (fresh * price["in"] + cached_tokens * price["cached"] + completion_tokens * price["out"]) / 1_000_000
