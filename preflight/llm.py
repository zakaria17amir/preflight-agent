"""Engine wrapper. Two backends, selected by PREFLIGHT_ENGINE (or --engine on the CLI):

  claude  -> `claude -p`  : reports exact cost_usd + tokens via --output-format json; has --max-turns and --tools ""
  devin   -> `devin -p`   : 48 model families (Claude, GPT, GLM, Gemini, DeepSeek, Kimi, SWE-*). Reports tokens via
                            --export (ATIF); dollars are ESTIMATED from `devin models list` list prices.
                            No hard turn cap (soft budget in the prompt) and no way to disable tools.

No API keys anywhere; each CLI owns its own auth.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

ENGINES = ("claude", "devin")


def engine() -> str:
    e = os.environ.get("PREFLIGHT_ENGINE", "claude").lower()
    if e not in ENGINES:
        raise RuntimeError(f"PREFLIGHT_ENGINE must be one of {ENGINES}, got {e!r}")
    return e


@dataclass
class LLMResult:
    text: str
    cost_usd: float
    input_tokens: int
    output_tokens: int
    num_turns: int
    duration_ms: int
    model: str
    engine: str = "claude"
    cost_estimated: bool = False
    raw: dict = field(default_factory=dict, repr=False)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


def _bin(name: str) -> str:
    exe = shutil.which(name)
    if not exe:
        raise RuntimeError(f"`{name}` CLI not found on PATH")
    return exe


def call(
    prompt: str,
    model: str = "haiku",
    cwd: Path | None = None,
    agentic: bool = False,
    timeout: int = 900,
    system: str | None = None,
    max_turns: int | None = None,
) -> LLMResult:
    """Run one non-interactive agent session on the configured engine.

    agentic=True lets the model use tools (read/edit/run) inside `cwd`; used for attempts.
    agentic=False is meant as a pure text call (brief/handoff). Exact on claude; best-effort on devin.
    """
    fn = _call_devin if engine() == "devin" else _call_claude
    return fn(prompt, model, cwd, agentic, timeout, system, max_turns)


# --- claude -----------------------------------------------------------------------------------------------


def _call_claude(prompt, model, cwd, agentic, timeout, system, max_turns) -> LLMResult:
    # --strict-mcp-config: ignore the user's MCP servers/plugins. Without it every call carries ~88k tokens of
    # tool schemas that have nothing to do with the task (measured: 10x the cost of a trivial call).
    cmd = [
        _bin("claude"),
        "-p",
        "--model",
        model,
        "--output-format",
        "json",
        "--strict-mcp-config",
        "--setting-sources",
        "project",
    ]
    cmd += ["--dangerously-skip-permissions"] if agentic else ["--tools", ""]
    if system:
        cmd += ["--append-system-prompt", system]
    if max_turns:
        cmd += ["--max-turns", str(max_turns)]
    proc = subprocess.run(
        cmd,
        input=prompt,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(cwd) if cwd else None,
        timeout=timeout,
    )
    out = proc.stdout.strip()
    start = out.find("{")
    if start < 0:
        raise RuntimeError(f"claude returned no JSON (exit {proc.returncode}): {proc.stderr[-500:]}")
    data = json.loads(out[start:])
    usage = data.get("usage", {})
    inp = (
        usage.get("input_tokens", 0)
        + usage.get("cache_creation_input_tokens", 0)
        + usage.get("cache_read_input_tokens", 0)
    )
    used_model = next(iter(data.get("modelUsage", {})), model)
    return LLMResult(
        text=data.get("result", "") or "",
        cost_usd=float(data.get("total_cost_usd", 0.0)),
        input_tokens=inp,
        output_tokens=usage.get("output_tokens", 0),
        num_turns=int(data.get("num_turns", 0)),
        duration_ms=int(data.get("duration_ms", 0)),
        model=used_model,
        engine="claude",
        raw=data,
    )


# --- devin ------------------------------------------------------------------------------------------------

# When preflight itself runs inside a Devin/Windsurf session these are inherited, and the devin CLI then
# switches to an embedded-auth mode and reports "Not logged in". Scrub them so the CLI uses credentials.toml.
_IDE_ENV = ("WINDSURF_IDE_TYPE", "ACP_BACKEND", "WINDSURF_EXT_HOST_PID")


def devin_env() -> dict:
    env = dict(os.environ)
    for k in _IDE_ENV:
        env.pop(k, None)
    return env


def _call_devin(prompt, model, cwd, agentic, timeout, system, max_turns) -> LLMResult:
    import time

    from . import pricing

    parts = []
    if system:
        parts.append(f"# Instructions\n{system}\n")
    if not agentic:
        parts.append(
            "# Constraint\nDo NOT use any tools (no file reads, no commands, no searches). "
            "Answer from the material in this message only.\n"
        )
    if max_turns:
        parts.append(
            f"# Budget\nYou may make at most {max_turns} tool calls. If you cannot finish within that, "
            "stop, make no further changes, and reply with what you found.\n"
        )
    parts.append(prompt)
    full = "\n".join(parts)

    with tempfile.TemporaryDirectory(prefix="preflight_devin_") as td:
        pfile, export = Path(td) / "prompt.md", Path(td) / "atif.json"
        pfile.write_text(full, encoding="utf-8")
        cmd = [
            _bin("devin"),
            "-p",
            "--prompt-file",
            str(pfile),
            "--model",
            model,
            "--respect-workspace-trust",
            "false",
            "--export",
            str(export),
        ]
        if agentic:
            cmd += ["--permission-mode", "dangerous"]
        t0 = time.time()
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(cwd) if cwd else None,
            timeout=timeout,
            env=devin_env(),
        )
        dur_ms = int((time.time() - t0) * 1000)
        if proc.returncode != 0 and not export.exists():
            raise RuntimeError(f"devin exited {proc.returncode}: {(proc.stderr or proc.stdout)[-500:]}")
        atif = json.loads(export.read_text(encoding="utf-8")) if export.exists() else {}

    fm = atif.get("final_metrics", {}) or {}
    prompt_toks = int(fm.get("total_prompt_tokens", 0))
    cached = int(fm.get("total_cached_tokens", 0))
    completion = int(fm.get("total_completion_tokens", 0))
    model_name = (atif.get("agent") or {}).get("model_name") or model
    price = pricing.lookup(model_name, pricing.load(env=devin_env()))
    est = pricing.estimate(prompt_toks, cached, completion, price)
    # ATIF "steps" include system/user/tool entries; agent turns are roughly half. Good enough for a budget signal.
    steps = int(fm.get("total_steps", 0))
    return LLMResult(
        text=proc.stdout.strip(),
        cost_usd=est if est is not None else 0.0,
        input_tokens=prompt_toks,
        output_tokens=completion,
        num_turns=max(1, steps // 2),
        duration_ms=dur_ms,
        model=model_name,
        engine="devin",
        cost_estimated=True,
        raw=dict(final_metrics=fm, price=price, priced=est is not None, model_requested=model),
    )
