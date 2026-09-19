---
name: repo-search
description: Locate relevant code and explain how the pieces connect
argument-hint: "<what to find>"
allowed-tools:
  - read
  - grep
  - glob
  - exec
triggers:
  - user
  - model
---

Find the code relevant to the user's request.

1. Inspect repository guidance and manifests first.
2. Search broadly for definitions, callers, tests, configuration, and documentation.
3. Trace the relevant flow end to end rather than stopping at the first match.
4. Report findings with precise file paths and line ranges.
5. Explain uncertainties and distinguish verified behavior from inference.

Do not modify files.
