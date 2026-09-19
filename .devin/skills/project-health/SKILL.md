---
name: project-health
description: Assess repository structure, changes, tests, and operational risks
allowed-tools:
  - read
  - grep
  - glob
  - exec
triggers:
  - user
---

Perform a project health assessment.

1. Read repository guidance and identify the language, frameworks, package managers, and CI workflows.
2. Inspect current changes and recent history when available.
3. Locate test, lint, typecheck, build, dependency-audit, and formatting commands.
4. Run safe, relevant verification commands, starting with targeted checks.
5. Review for obvious security, maintenance, and release risks.
6. Summarize what is healthy, what failed, evidence for each finding, and prioritized next actions.

Do not deploy, publish, mutate external services, or make code changes unless the user separately requests them.
