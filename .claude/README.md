# `.claude/` helper set

Productivity helpers for spec-driven work in `living-doc-generator-markdown`. The set is copied from
`living-doc-collector-gh`, the reference copy for the `living-doc-*` ecosystem, with the repo-specific
parts (the mock/fixture table, the doc paths) adapted to this repository.

These helpers are **acceleration, not dependency**. Every task they describe can be done by
hand, just slower. Nothing in CI or the release path requires them.

## What's here

| File | Kind | Purpose |
|---|---|---|
| `commands/implement-task.md` | slash command | Drive a task from its GitHub issue or owner-provided brief, through acceptance criteria, to a PR-ready description. |
| `commands/verify-pr-ready.md` | slash command | Convergent review loop before a PR: verified findings in a ledger, delta re-review, one yes/no. |
| `agents/test-author.md` | subagent | Write deterministic pytest tests using this repo's real mock surface. |

## How the two commands relate

Both check **acceptance criteria against the actual code** — reading the return annotation,
the sort call, the guard position — never "a test with that name is green".

- **`/implement-task <id>`** is the full lifecycle: read the task → read every referenced
  file → implement → `make qa` until green → verify each acceptance criterion against code
  → write the `## Overview` / `## Release Notes` / `## Related` PR description → stop. It
  collapses the `specification-master` → `senior-developer` → `sdet` → `reviewer` agent
  sequence into one driven command.

- **`/verify-pr-ready <id>`** is the final gate before opening a PR — useful when a human
  did most of the implementation. It runs a bounded loop: acceptance criteria against code,
  `make qa`, one fresh `reviewer` per area of the diff (every file gets a coverage line),
  independent verification of each finding, fixes for confirmed Blocker/Important rows,
  then a re-review of the fix diff only — at most 3 fix rounds. Findings live in a
  gitignored ledger under `.review/<id>/`, so a later session resumes instead of starting a
  new full review. Output is a single `PR-READY: yes/no`. It never commits or pushes.

Typical flow: `/implement-task` to build it, then `/verify-pr-ready` as the final gate
before opening the PR.

## Relationship to `.github/agents/`

The `.github/agents/` board (`specification-master`, `senior-developer`, `sdet`,
`reviewer`, `devops-engineer`) stays the source of truth for role behavior. `test-author`
here is `sdet` plus the concrete repo mock table (see `test-author.md`'s "Mock / fixture
cheat-table"); `/verify-pr-ready` invokes `reviewer`.
