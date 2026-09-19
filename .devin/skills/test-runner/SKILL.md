---
name: test-runner
description: Discover and run the smallest relevant project verification commands
argument-hint: "[scope]"
allowed-tools:
  - read
  - grep
  - glob
  - exec
triggers:
  - user
---

Validate the requested scope.

1. Read repository guidance, manifests, and existing CI configuration to discover supported commands.
2. Start with the smallest targeted test, lint, typecheck, or build command that covers the change.
3. Expand verification only when warranted by dependencies or failures.
4. Do not alter security settings, dependency policies, snapshots, or tests merely to make checks pass.
5. Report each command, its result, and any remaining verification gap.

If a command could deploy, publish, migrate, delete data, or otherwise cause external side effects, ask before running it.
