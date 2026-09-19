---
name: code-review
description: Review current changes for correctness, security, and maintainability
allowed-tools:
  - read
  - grep
  - glob
  - exec
triggers:
  - user
  - model
---

Review the current repository changes.

1. Read repository guidance and determine the intended change from the diff and nearby code.
2. Trace affected callers, data flows, tests, and configuration.
3. Prioritize concrete defects: correctness, regressions, security, data loss, concurrency, performance, and missing tests.
4. Run targeted read-only checks when useful.
5. Report findings in severity order with file and line references, followed by assumptions and a short summary.

Do not modify files. Avoid speculative style feedback unless it affects correctness or maintainability.
