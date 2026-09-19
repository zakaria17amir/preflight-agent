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
units and a report). Issues are written like a human would write them: symptoms only, **no file names**. Six arms
per bug, each verified by the repo's 21 tests:

| arm | what it is | tests the claim |
|---|---|---|
| **A** `cold_strong` | sonnet, issue text only | "just use the expensive model" |
| **B** `brief_cheap` | haiku, issue + brief | does orientation let a cheap model do the job? |
| **C** `cascade` | brief → haiku → handoff → sonnet | start cheap, escalate *informed* |
| **D** `cascade_nohandoff` | brief → haiku → sonnet (clean restart) | control for C |
| **E** `capped_handoff` | like C, but haiku gets only 4 tool calls | forces escalation; is a cheap failure informative? |
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
<!-- /RESULTS_TABLE -->

Costs are total dollars per bug **including** the brief and handoff calls (the overhead is part of the price).
Full per-run records with briefs, handoffs, diffs and test output: `bench/results/runs/`.

### What the table says (n=5, one run per cell, so read as directional)

1. **Orientation works.** Haiku with a brief (B) solved 5/5 for **$0.42 vs $0.62** for cold sonnet (A): same pass
   rate, 32% cheaper, including the ~$0.01 the brief costs. The brief put the right file first every time
   (`tests/test_preflight.py::test_scan_ranks_the_right_file_for_each_bug` checks the zero-token ranking alone
   does this).
2. **The cascade never escalated.** In C and D, briefed haiku solved every bug, including the L one. So on this repo
   C ≈ B ≈ D and the difference between them is run-to-run noise (~10%). Good for the "start cheap" thesis, useless
   for testing the handoff.
3. **Starting cheap can lose. It did here.** Forcing escalation with a 4-tool-call cap (E) cost **$0.72, 16% more
   than just using sonnet.** Three of five haiku attempts hit the cap with an empty diff, so the cheap attempt bought
   nothing and the cascade paid twice. F came in at $0.43 only because haiku happened to finish inside the cap
   on 4/5 bugs. The E–F gap is variance in *whether haiku finished*, not the handoff.
4. **Handoff vs clean restart: one paired data point.** On `unit_to_base` both E and F escalated and both passed;
   with handoff $0.225, without $0.212. The handoff call itself cost $0.011. No conclusion at n=1.
5. **The most useful observation:** a budget-cap failure is an *uninformative* failure. The handoff for
   `power_assoc` correctly reported "no code changes; diff empty; likely ran out of budget" and had little to
   distill. A handoff can only carry information the cheap attempt produced. That means the escalation gate matters
   more than the handoff format: escalate on *wrong patch*, not on *no patch* (Darwin Cascade's empty-patch gate
   is the opposite policy: retry cheap on empty, and their data supports it).

### Read this before believing the table

- **n=5, one run each.** Agent runs are stochastic. This is a pilot that shows the harness works and where the
  effect is plausible, not a result. `python bench/run_bench.py --redo` reruns everything; the table regenerates.
- **Toy repo.** ~300 lines, 7 files. Orientation cost is small here, so the *brief* arm understates the benefit
  it would have on a real 50k-line codebase, and the *cascade* overstates how often haiku wins.
- **The cheap tier is very cheap.** Haiku vs sonnet is ~3-5x on list price. A cascade beating cold-strong on cost
  is nearly guaranteed when the cheap tier wins; the interesting cells are the ones where it doesn't (arm E).
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
python -m preflight cascade path/to/repo "..." --tiers haiku,sonnet --cheap-max-turns 6   # keep failure cheap

# distill a failed attempt into a v2 brief by hand
python -m preflight handoff "issue text" BRIEF.md failed_attempt.log -o BRIEF.v2.md

# the experiment
python bench/run_bench.py            # arms A,B,C; resumable; skips (bug, arm) pairs already recorded
python bench/run_bench.py --arms D_cascade_nohandoff,E_capped_handoff,F_capped_nohandoff --cheap-turns 4
python bench/run_bench.py --redo --bugs power_assoc --arms C_cascade
python -m pytest -q                  # preflight's own tests (scan ranking, size parsing, every bug breaks the target)
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
  target/      calcx: the clean repo (21 tests, all green)
  bugs.py      5 seeded mutations (S,S,M,M,L) + human-style issue text
  run_bench.py arms A-F, per-run JSON records, results.json, markdown table (also injected above)
```

## What's already known, and what this adds

Model cascades and routers for coding agents are an active area: SWE-Router (route after a few cheap exploratory
turns), Darwin Cascade (escalate on empty patch, 51% SWE-bench Lite at $0.27/instance), CodeRescue (learned
cheap-retry vs escalate), RouteLLM. The *brief* half is what `AGENTS.md` / repo maps do statically.

What is not cleanly measured, as far as we found: whether a **distilled failure brief** handed up a cascade beats
a **clean restart** at the stronger tier. The contamination result says raw retries hurt; Reflexion says structured
post-mortems help within a model. `preflight` is the harness to test that in the cross-tier case (arms E vs F);
this run is the pilot, and its one paired data point is a tie. The pilot's real lesson is upstream of that
question: with a budget-cap gate most cheap failures are empty, so there is nothing to hand off. Run it with a
*wrong-patch* gate on a repo hard enough that haiku actually produces wrong patches.

## Cut list (what a longer version does)

- Arm G: raw-transcript handoff, to measure contamination directly against D (clean) and C (distilled).
- n=10+ per cell. Every cell above is one stochastic agent run.
- Escalation gate: "tests still fail after a non-empty patch" instead of a turn cap, so failures are informative.
- Brief caching per repo: the scan and conventions are reusable across issues; only "Start here" is per-issue.
- Use the brief's tier recommendation to *choose* the first tier instead of always starting at haiku.
- Real repos: run on SWE-bench Lite instances with the same arms.
