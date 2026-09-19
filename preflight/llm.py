"""Thin wrapper over the `claude -p` CLI. No API key handling; the CLI owns auth."""
from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

TIERS = {"cheap": "haiku", "mid": "sonnet", "strong": "opus"}


@dataclass
class LLMResult:
    text: str
    cost_usd: float
    input_tokens: int
    output_tokens: int
    num_turns: int
    duration_ms: int
    model: str
    raw: dict = field(default_factory=dict, repr=False)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


def _claude_bin() -> str:
    exe = shutil.which("claude")
    if not exe:
        raise RuntimeError("`claude` CLI not found on PATH")
    return exe


def call(prompt: str, model: str = "haiku", cwd: Path | None = None, agentic: bool = False,
         timeout: int = 900, system: str | None = None, max_turns: int | None = None) -> LLMResult:
    """Run one non-interactive claude session.

    agentic=True lets the model use tools (read/edit/run) inside `cwd`; used for attempts.
    agentic=False is a pure text call; used for brief/handoff generation.
    """
    # --strict-mcp-config: ignore the user's MCP servers/plugins. Without it every call carries ~88k tokens of
    # tool schemas that have nothing to do with the task (measured: 10x the cost of a trivial call).
    cmd = [_claude_bin(), "-p", "--model", model, "--output-format", "json", "--strict-mcp-config",
           "--setting-sources", "project"]
    if agentic:
        cmd += ["--dangerously-skip-permissions"]
    else:
        cmd += ["--tools", ""]
    if system:
        cmd += ["--append-system-prompt", system]
    if max_turns:
        cmd += ["--max-turns", str(max_turns)]
    proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", cwd=str(cwd) if cwd else None, timeout=timeout)
    out = proc.stdout.strip()
    start = out.find("{")
    if start < 0:
        raise RuntimeError(f"claude returned no JSON (exit {proc.returncode}): {proc.stderr[-500:]}")
    data = json.loads(out[start:])
    usage = data.get("usage", {})
    inp = usage.get("input_tokens", 0) + usage.get("cache_creation_input_tokens", 0) + usage.get("cache_read_input_tokens", 0)
    used_model = next(iter(data.get("modelUsage", {})), model)
    return LLMResult(
        text=data.get("result", "") or "",
        cost_usd=float(data.get("total_cost_usd", 0.0)),
        input_tokens=inp,
        output_tokens=usage.get("output_tokens", 0),
        num_turns=int(data.get("num_turns", 0)),
        duration_ms=int(data.get("duration_ms", 0)),
        model=used_model,
        raw=data,
    )
