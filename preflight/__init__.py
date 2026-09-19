"""preflight: the tech-lead pass before a coding agent runs.

brief   -> orient the agent (where to start, conventions, how to test, size + tier)
run     -> one agent attempt at a given tier, verified by the repo's tests
handoff -> distill a failed attempt into an enriched brief for the next tier
cascade -> cheap tier first, escalate with the handoff brief on failure
"""
