# preflight

**Brief the agent, size the job, start cheap.**

**Live dashboard:** https://zakaria17amir.github.io/preflight-agent/ — every result below, per-model analytics, and
a recorded cascade run. (Static snapshot of the committed results; agent runs happen on your machine, see *Live demo*.)

A tech-lead pass that runs *before* a coding agent does: it orients the agent, sizes the task, tries the cheap
model first, and escalates with a distilled post-mortem when that fails. Built in a 3-hour hackathon, with a
measured experiment instead of a promise.

```
issue ──▶ scan (0 tokens) ──▶ brief (haiku, ~$0.01) ──▶ attempt: haiku ──▶ tests pass? ──▶ done
                                                              │ fail
                                                              ▼
                                                    handoff (post-mortem) ──▶ attempt: sonnet ──▶ tests
```

## TL;DR of the results

| engine | | pass | cost for 5 bugs | vs sonnet alone |
|---|---|---|---|---|
| claude | Sonnet, cold | 5/5 | $0.62 | — |
| claude | **Haiku + brief** | 5/5 | **$0.42** | **−32%** |
| claude | Cascade, forced to escalate on 3/5 | 5/5 | $0.72 | **+16%** |
| devin | Sonnet, cold | 5/5 | $0.25 est. | — |
| devin | **GPT-5.6 Luna + brief** (brief written by haiku) | 5/5 | **$0.07 est.** | **−74%** |

- A **$0.01 brief** let the cheap model match the expensive one at a third less cost.
- The brief is **portable across vendors**: a Claude-written brief handed to a GPT agent through Devin CLI got
  5/5 at a quarter of cold Sonnet's cost. Compare within an engine row only: Devin dollars are list-price
  estimates and its Sonnet is a different model/harness than the Claude CLI's.
- **Starting cheap can lose**, and did when the cheap tier was budget-capped: failed cheap attempts were empty,
  so the cascade paid twice and the handoff had nothing to carry.
- The lesson is upstream of "handoff vs clean restart": **the escalation gate matters more than the handoff.**
  Escalate on *wrong patch*, not *no patch*.

n = 5 bugs × 1 run per cell, toy repo. Directional, not a result. Details and caveats below.

## Why

You pay a coding agent the same whether the task is a typo or a refactor, and you hand it the same thin issue
either way. Two wastes follow: the agent spends its first stretch **orienting** (reading files, guessing
conventions, sometimes editing the wrong module), and every task gets the **frontier model** regardless of size.
`preflight` attacks both: brief first, size the job, spend accordingly.

## Live demo (about 2 minutes)

```bash
python -m preflight demo power_assoc        # seeds a bug into a scratch copy of calcx, writes ISSUE.md
python -m preflight scan  <scratch> ISSUE.md      # zero tokens: right file ranked first
python -m preflight cascade <scratch> ISSUE.md --tiers haiku,sonnet --cheap-max-turns 2
```

Progress streams to stderr as it happens: scan → brief (printed) → haiku attempt with a 2-tool-call budget →
tests → diff → **escalation** → handoff (printed) → sonnet attempt → tests → diff → per-stage cost table.
Use `--cheap-max-turns 3` or higher and haiku usually solves it alone; drop the flag for the real policy.
Nothing touches your tree: every attempt runs in a fresh `git init`-ed copy under `%TEMP%`, and the path is printed.

Real repo: [`examples/click_progressbar_BRIEF.md`](examples/click_progressbar_BRIEF.md) is the brief for a
symptom-only issue against a fresh clone of pallets/click (~100 files). **$0.018, 14 s.** It puts
`src/click/_termui_impl.py` first (where `ProgressBar` lives), names the `-k progressbar` test selector, calls
it M / mid, and warns not to change `update(n)`.

## Commands

| command | what it does | tokens |
|---|---|---|
| `scan <repo> <issue>` | file tree, README, test command, conventions, files ranked by issue keywords | 0 |
| `brief <repo> <issue>` | scan → haiku → `BRIEF.md`: start-here files, conventions, verify, risks, **size S/M/L, tier** | ~9k |
| `run <repo> <issue> [--brief B] [--model M] [--max-turns N]` | one agent attempt in a scratch copy; the repo's tests decide | agent |
| `handoff <issue> <brief> <log> [--repo R]` | failed attempt → structured post-mortem brief (v2), grounded on the scan | ~9k |
| `cascade <repo> <issue> [--tiers a,b] [--cheap-max-turns N] [--no-handoff]` | tiers in order, handoff between them, per-stage costs | agent |
| `demo [bug]` | seed a bench bug into a scratch copy for a live demo | 0 |

## Engines

`preflight` drives an agent CLI as a subprocess. No API keys, no SDK; each CLI owns its own auth.
Pick with `--engine` (or `PREFLIGHT_ENGINE`).

| | `--engine claude` (default) | `--engine devin` |
|---|---|---|
| Binary | Claude Code CLI, `claude -p` | Devin CLI, `devin -p` |
| Models | Claude only (`haiku`, `sonnet`, `opus`) | **48 families**: Claude, GPT-5.x, GLM, Gemini, DeepSeek, Kimi, Grok, SWE-1.6/2 |
| Cost | **exact** `total_cost_usd` from `--output-format json` | **estimated**: tokens from the ATIF `--export`, priced at the list prices `devin models list` prints. Labelled `est` everywhere |
| Turn budget (`--cheap-max-turns`) | hard, `--max-turns` | soft: stated in the prompt, no enforcement |
| No-tools text calls (brief, handoff) | `--tools ""` | best-effort instruction; the model may still read files |
| Overhead per call | ~7k tokens with `--strict-mcp-config` (88k without) | ~11–15k tokens |

Why Devin matters here: it turns the cascade **cross-provider**. Haiku → Sonnet is a 3–5× price gap inside one
vendor and haiku already solves everything. With Devin the cheap tier can be **GPT-5.6 Luna ($0.20/1M in)**, GLM,
or **SWE-2 (free)** and the strong tier Sonnet or Opus: a 10–25× gap, a weaker cheap tier that actually fails,
and one haiku-written brief handed to a different model family — is orientation portable across vendors?

```bash
python -m preflight --engine devin cascade <repo> ISSUE.md --tiers gpt-5.6-luna,sonnet
python -m preflight --engine devin cascade <repo> ISSUE.md --tiers swe-2,opus
python bench/run_bench.py --engine devin --cheap gpt-5.6-luna --strong sonnet --arms A_cold_strong,B_brief_cheap,C_cascade
```

Results from other engines / tier pairs are kept as separate arms (`B_brief_cheap@devin_gpt-5.6-luna-to-sonnet`) so
exact and estimated dollars never get summed together. Gotcha we hit: when `preflight` itself runs inside a
Devin/Windsurf session, the `devin` CLI inherits IDE env vars and reports "Not logged in"; `preflight/llm.py`
scrubs them.

Requires Python 3.11+ and a logged-in `claude` and/or `devin` CLI. No other dependencies.

## The experiment

`bench/target` is **calcx**: tokenizer → recursive-descent parser → evaluator, with unit conversion and a text
report. ~300 lines, 7 files, 21 tests. `bench/bugs.py` seeds five bugs (S, S, M, M, L) and pairs each with an
issue written the way a human writes one: **symptoms only, no file names.**

| arm | what it is | tests the claim |
|---|---|---|
| **A** `cold_strong` | sonnet, issue text only | "just use the expensive model" |
| **B** `brief_cheap` | haiku, issue + brief | does orientation let a cheap model do the job? |
| **C** `cascade` | brief → haiku → handoff → sonnet | start cheap, escalate *informed* |
| **D** `cascade_nohandoff` | brief → haiku → sonnet (clean restart) | control for C |
| **E** `capped_handoff` | like C, haiku limited to 4 tool calls | forces escalation; is a cheap failure informative? |
| **F** `capped_nohandoff` | like E, clean restart | control for E: isolates the handoff |

<!-- RESULTS_TABLE -->
| bug | size | A_cold_strong | B_brief_cheap | C_cascade | D_cascade_nohandoff | E_capped_handoff | F_capped_nohandoff |
|---|---|---|---|---|---|---|---|
| report_counter | S | PASS $0.083 | PASS $0.055 | PASS $0.064 (haiku) | PASS $0.065 (haiku) | PASS $0.154 (sonnet) | PASS $0.055 (haiku) |
| fahrenheit | S | PASS $0.105 | PASS $0.091 | PASS $0.059 (haiku) | PASS $0.062 (haiku) | PASS $0.064 (haiku) | PASS $0.053 (haiku) |
| power_assoc | M | PASS $0.092 | PASS $0.082 | PASS $0.058 (haiku) | PASS $0.087 (haiku) | PASS $0.147 (sonnet) | PASS $0.056 (haiku) |
| leading_dot | M | PASS $0.169 | PASS $0.076 | PASS $0.076 (haiku) | PASS $0.073 (haiku) | PASS $0.132 (sonnet) | PASS $0.056 (haiku) |
| unit_to_base | L | PASS $0.174 | PASS $0.117 | PASS $0.124 (haiku) | PASS $0.128 (haiku) | PASS $0.225 (sonnet) | PASS $0.212 (sonnet) |
| **total** | | **5/5 pass, $0.623** | **5/5 pass, $0.421** | **5/5 pass, $0.380** | **5/5 pass, $0.415** | **5/5 pass, $0.721** | **5/5 pass, $0.431** |

Other engines / tier pairs (devin $ are list-price estimates):

| bug | size | A_cold_strong@devin_gpt-5.6-luna-to-sonnet | B_brief_cheap@devin_gpt-5.6-luna-to-sonnet | C_cascade@devin_gpt-5.6-luna-to-sonnet |
|---|---|---|---|---|
| report_counter | S | PASS $0.042 | PASS $0.016 | PASS $0.018 (gpt-5.6-luna) |
| fahrenheit | S | PASS $0.043 | PASS $0.011 | PASS $0.018 (gpt-5.6-luna) |
| power_assoc | M | PASS $0.045 | PASS $0.011 | PASS $0.018 (gpt-5.6-luna) |
| leading_dot | M | PASS $0.052 | PASS $0.015 | PASS $0.012 (gpt-5.6-luna) |
| unit_to_base | L | PASS $0.070 | PASS $0.014 | PASS $0.017 (gpt-5.6-luna) |
| **total** | | **5/5 pass, $0.253** | **5/5 pass, $0.067** | **5/5 pass, $0.082** |
<!-- /RESULTS_TABLE -->

Other engines / tier pairs (devin $ are list-price estimates):

| bug | size | A_cold_strong@devin_gpt-5.6-luna-to-sonnet | B_brief_cheap@devin_gpt-5.6-luna-to-sonnet | C_cascade@devin_gpt-5.6-luna-to-sonnet |
|---|---|---|---|---|
| report_counter | S | PASS $0.042 | PASS $0.016 | PASS $0.018 (gpt-5.6-luna) |
| fahrenheit | S | PASS $0.043 | PASS $0.011 | PASS $0.018 (gpt-5.6-luna) |
| power_assoc | M | PASS $0.045 | PASS $0.011 | PASS $0.018 (gpt-5.6-luna) |
| leading_dot | M | PASS $0.052 | PASS $0.015 | PASS $0.012 (gpt-5.6-luna) |
| unit_to_base | L | PASS $0.070 | PASS $0.014 | PASS $0.017 (gpt-5.6-luna) |
| **total** | | **5/5 pass, $0.253** | **5/5 pass, $0.067** | **5/5 pass, $0.082** |
<!-- /RESULTS_TABLE -->



Costs include the brief and handoff calls. `(haiku)`/`(sonnet)` is the tier that produced the passing patch.
Every run's brief, handoff, diff, test output and agent summary is in `bench/results/runs/<bug>.<arm>.json`.

### What it says

1. **Orientation works.** B matched A at 5/5 for 32% less, including the brief's cost. The zero-token scan alone
   ranks the right file top-3 for every bug (`tests/test_preflight.py::test_scan_ranks_the_right_file_for_each_bug`).
2. **The cascade never escalated** in C or D: briefed haiku solved everything, including the L bug. Good for
   "start cheap", useless for testing the handoff. C ≈ B ≈ D; the spread is run-to-run noise.
3. **Forced escalation lost money.** E (4-tool-call cap) cost 16% more than sonnet alone. Three of five haiku
   attempts hit the cap with an empty diff. F was cheaper only because haiku happened to finish inside the cap
   4 times out of 5; the E–F gap is variance in *whether haiku finished*, not the handoff.
4. **Handoff vs clean restart: one paired point.** Both E and F escalated on `unit_to_base`; both passed;
   $0.225 with handoff vs $0.212 without. No conclusion at n = 1.
5. **Cross-vendor, the brief still carries.** On Devin CLI, GPT-5.6 Luna ($0.20/1M in) with the haiku brief went
   5/5 at $0.067 est. vs $0.253 est. for cold Sonnet, and never escalated. The orientation is not Claude-specific;
   it is just a good delegation note. (Wider price gap than haiku→sonnet, so the "start cheap" saving is larger,
   but the cheap tier *still* didn't fail, so the handoff remains untested here too.)
6. **A budget-cap failure is uninformative.** The `power_assoc` handoff correctly said "no code changes, diff
   empty" and had nothing to distill. A handoff can only carry what the cheap attempt produced, so the gate
   decides whether the cheap attempt is an investment or a tax. (Darwin Cascade's gate is the mirror image:
   retry cheap on *empty* patch. Their data supports it.)

<details>
<summary><b>Caveats: read before believing the table</b></summary>

- **One run per cell.** Agent runs are stochastic; ±10% between identical arms is normal here.
- **Toy repo.** Orientation is cheap on 7 files, so B understates the brief's value on a 50k-line codebase, and
  C/D overstate how often haiku wins.
- **Haiku is very cheap** (3–5× under sonnet on list price). A cascade beating cold-strong is nearly guaranteed
  when the cheap tier wins; the informative cells are the ones where it doesn't.
- **~7k tokens of fixed CLI overhead per call**, identical across arms. Absolute costs are higher than raw API.
- **Bugs were seeded by us.** A seeded bug has a known one-line fix; real issues often don't.
</details>

### Reproduce

```bash
python -m pytest -q                                  # 12 tests: scan ranking, size parsing, every bug breaks the target
python bench/run_bench.py                            # arms A,B,C; resumable
python bench/run_bench.py --arms D_cascade_nohandoff,E_capped_handoff,F_capped_nohandoff --cheap-turns 4
python bench/run_bench.py --redo --bugs power_assoc --arms C_cascade
```

The table above is regenerated into this README on every run. Pushing `bench/results/**` to `main` redeploys the
dashboard to GitHub Pages (`.github/workflows/pages.yml`); the site is the committed results, nothing runs there.

## What we found while building it

- **The handoff model hallucinated tool calls.** The post-mortem is a no-tools text call; on the demo it emitted
  fake `<function_calls>` blocks and invented a `parse_power()` function that doesn't exist. Sonnet still fixed the
  bug (it read the code itself), but a handoff that fabricates is worse than none. Fixed by telling the model it has
  no tools, grounding it with the zero-token scan (real file names), and stripping any tool-call markup
  (`preflight/handoff.py::sanitize`, tested).
- **88k tokens of CLI overhead per call** until `--strict-mcp-config`. Measure your harness before your prompt.
- **A seeded bug that broke no test** slipped through until the guard test caught it. Every bench bug now has a
  test proving it fails on the clean target.

## Related work and what this adds

Cascades and routers for coding agents are an active area: SWE-Router (route after a few cheap exploratory turns),
Darwin Cascade (escalate on empty patch; 51% SWE-bench Lite at $0.27/instance), CodeRescue (learned cheap-retry vs
escalate), RouteLLM. The brief half is what `AGENTS.md` and repo maps do statically. The contamination result
(arxiv 2605.08563) says leaving a failed transcript in context makes retries worse; Reflexion says a structured
post-mortem helps within one model.

Not cleanly measured, as far as we found: whether a **distilled failure brief handed up a cascade beats a clean
restart at the stronger tier.** Arms E vs F are the harness for that. This pilot's one paired point is a tie, and
its real lesson is that with a budget-cap gate most cheap failures are empty. Run it with a *wrong-patch* gate on
a repo where haiku produces wrong patches.

## Next

- Gate on "non-empty patch, tests still fail" instead of a turn cap, so escalations are informative.
- Arm G: raw-transcript handoff, to measure contamination directly against C (distilled) and D (clean).
- n ≥ 10 per cell; then SWE-bench Lite instances with the same arms.
- Use the brief's tier call to pick the *first* tier instead of always starting at haiku.
- Cache the scan and conventions per repo; only "Start here" is per-issue.

## Layout

```
preflight/
  scan.py      deterministic repo scan (tree, README, test cmd, conventions, keyword-ranked files)
  brief.py     scan -> BRIEF.md via cheap model; parses size/tier; heuristic size as a sanity check
  run.py       one attempt in a fresh git-initialised copy; tests decide; captures diff + transcript
  handoff.py   failed attempt -> grounded post-mortem brief; strips hallucinated tool calls
  cascade.py   tiers in order, handoff between them, per-stage cost accounting
  llm.py       engine wrapper: `claude -p` (exact $) or `devin -p` (48 model families, $ estimated)
  pricing.py   list-price table parsed from `devin models list`; tokens -> estimated $
  log.py       stage-by-stage progress to stderr
bench/
  target/      calcx, the clean repo (21 tests)
  bugs.py      5 seeded mutations (S,S,M,M,L) + human-style issue text
  run_bench.py arms A-F; per-run JSON records are the source of truth; regenerates the table above
  results/     results.json, table.md, runs/*.json
examples/      brief on pallets/click
tests/         preflight's own tests
```

Security note: attempts run `claude` with `--dangerously-skip-permissions` inside the scratch copy. The copy
isolates your tree, not your machine; the agent can still run shell commands. Don't point it at anything you
wouldn't let a contractor `rm -rf`.
