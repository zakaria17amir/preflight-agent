# preflight

**Brief the agent, size the job, start cheap.**

Most of what you pay a coding agent goes to two things that produce no code: *orientation* (figuring out where
things live in a repo it has never seen) and *overkill* (running a frontier model on a one-line fix).
`preflight` sits in front of the agent and does what a tech lead does before delegating:

1. **`brief`** — scans the repo deterministically (zero tokens), then has a cheap model write a short delegation
   brief: where to start, conventions, how to verify, risks, a **size call (S/M/L)** and a **tier recommendation**.
2. **`run`** — one agent attempt at a chosen tier, in a scratch copy, verified by the repo's own tests.
3. **`handoff`** — when an attempt fails, distill *what was tried, why it failed, what's ruled out* into an
   enriched brief. Not the raw transcript: a failed transcript left in context anchors the next attempt on the
   same wrong path ([context contamination](https://arxiv.org/abs/2605.08563)). A structured post-mortem is a
   different treatment, and whether it beats a cold restart is the question this repo measures.
4. **`cascade`** — cheap tier first; on failure, handoff and escalate.

Engine: the `claude` CLI in `-p` (print) mode as a subprocess. No API keys, no SDK; `--output-format json`
gives real per-call `cost_usd` and token counts, which is where the numbers below come from.

## The number

Five bugs seeded into a small Python package (`bench/target`, a tokenizer → parser → evaluator calculator with
units and a report). Issues are written like a human would write them: symptoms only, **no file names**. Three arms
per bug, each verified by the repo's 20 tests:

| arm | what it is | tests the claim |
|---|---|---|
| **A** `cold_strong` | sonnet, issue text only | "just use the expensive model" |
| **B** `brief_cheap` | haiku, issue + brief | does orientation let a cheap model do the job? |
| **C** `cascade` | brief → haiku → handoff → sonnet | start cheap, escalate *informed* |

<!-- RESULTS_TABLE -->

Costs are total dollars per bug **including** the brief and handoff calls (the overhead is part of the price).
Full per-run records with briefs, handoffs, diffs and test output: `bench/results/runs/`.

### Read this before believing the table

- **n=5, one run each.** Agent runs are stochastic. This is a pilot that shows the harness works and where the
  effect is plausible, not a result. `python bench/run_bench.py --redo` reruns everything; the table regenerates.
- **Toy repo.** ~300 lines, 7 files. Orientation cost is small here, so the *brief* arm understates the benefit
  it would have on a real 50k-line codebase, and the *cascade* overstates how often haiku wins.
- **The cheap tier is very cheap.** Haiku vs sonnet is ~3-5x on list price. A cascade beating cold-strong on cost
  is nearly guaranteed when the cheap tier wins; the interesting cell is what happens on the L bug where it doesn't.
- **Fixed CLI overhead.** Every `claude -p` call carries ~7k tokens of harness prompt (it was 88k before
  `--strict-mcp-config`; see `preflight/llm.py`). It's the same across arms so it doesn't bias comparisons,
  but it means absolute costs are higher than a raw API call would be.

## Try it

```bash
# what the LLM sees about the repo: deterministic, zero tokens
python -m preflight scan  path/to/repo "users report X happens when Y"

# the brief (haiku by default)
python -m preflight brief path/to/repo "users report X happens when Y" -o BRIEF.md

# one attempt at a tier, tests decide pass/fail; works on a temp copy, never touches your tree
python -m preflight run   path/to/repo "..." --brief BRIEF.md --model haiku

# cheap first, escalate with handoff on failure
python -m preflight cascade path/to/repo "..." --tiers haiku,sonnet

# the experiment
python bench/run_bench.py            # resumable; skips (bug, arm) pairs already recorded
python bench/run_bench.py --redo --bugs power_assoc --arms C_cascade
```

Requires Python 3.11+ and the `claude` CLI logged in. No other dependencies.

## Layout

```
preflight/
  scan.py      deterministic repo scan: tree, README, test cmd, conventions, keyword-ranked files (zero tokens)
  brief.py     scan -> BRIEF.md via cheap model; parses size/tier; heuristic size as a sanity check
  run.py       one attempt in a fresh git-initialised copy; tests decide; captures diff + transcript
  handoff.py   failed attempt -> structured post-mortem brief for the next tier
  cascade.py   tiers in order, handoff between them, per-stage cost accounting
  llm.py       `claude -p` wrapper returning text + cost + tokens
bench/
  target/      calcx: the clean repo (20 tests, all green)
  bugs.py      5 seeded mutations (S,S,M,M,L) + human-style issue text
  run_bench.py the three arms, results.json, markdown table
```

## What's already known, and what this adds

Model cascades and routers for coding agents are an active area: SWE-Router (route after a few cheap exploratory
turns), Darwin Cascade (escalate on empty patch, 51% SWE-bench Lite at $0.27/instance), CodeRescue (learned
cheap-retry vs escalate), RouteLLM. The *brief* half is what `AGENTS.md` / repo maps do statically.

What is not cleanly measured, as far as we found: whether a **distilled failure brief** handed up a cascade beats
a **clean restart** at the stronger tier. The contamination result says raw retries hurt; Reflexion says structured
post-mortems help within a model. `preflight` is the harness to test that in the cross-tier case; the bench here
is the pilot. The next arm to add is `C'`: cascade with `--no-handoff` (clean restart at sonnet), which isolates
the handoff's contribution from the cascade's.

## Cut list (what a longer version does)

- Arm C' (`--no-handoff`) and arm D (raw transcript handoff) to isolate the handoff effect.
- Brief caching per repo: the scan and conventions are reusable across issues; only "Start here" is per-issue.
- Use the brief's tier recommendation to *choose* the first tier instead of always starting at haiku.
- Real repos: run on SWE-bench Lite instances with the same three arms.
