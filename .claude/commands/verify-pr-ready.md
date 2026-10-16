---
description: Verify a branch is PR-ready with a convergent review loop — partitioned full review, verified findings, a persistent ledger, delta re-review. Outputs one yes/no.
argument-hint: <task-id or issue number> (e.g. 2) [path-or-URL to the brief, if not the issue]
---

You are the final gate before a PR is opened. Assume a human (or a prior run) did most of
the implementation. You run a **bounded, convergent** review loop: every changed file is
reviewed, every finding is verified and recorded in a ledger, confirmed findings are fixed,
and only the fix diff is re-reviewed. A later session reads the ledger instead of starting
over.

Task ID: `$1`
Brief source (optional override): `$2`

Do not open the PR, push, or commit — at any step.

## Why this shape

A single reviewer pass over a large diff reads only a part of it closely, and a capped
reviewer reports only its top findings — so each fresh session surfaces a different few, and
the same session, anchored on its own findings, sees nothing new. The loop removes each
cause: partitioning plus a coverage record (no file skipped), no cap (no drip-feed), a
failure-scenario bar (findings run out), a ledger (no re-litigating), fresh-context
reviewers (no anchoring).

## Severity bar — applies to every finding

- **Blocker** — an acceptance criterion not met, a red `make qa` gate, a contract break
  (see `reviewer.agent.md` "Contract-sensitive outputs"), or a defect on the PR's primary
  path: a documented, typical input crashes the run, loses or corrupts output, or leaks a
  secret.
- **Important** — any other defect with a concrete failure scenario: an edge-case input or
  state → wrong output, crash, lost data; or a misleading doc statement a user would act on.
- **Nit** — everything else, including any finding that cannot state a failure scenario.
  Nits are recorded, never block, and are never fixed by this loop.

## 0. Freeze the scope (skip what already exists)

Work in `.review/$1/` (gitignored). If it already exists, read it and resume at the step
the ledger's `## Rounds` section says comes next — do not restart.

- `ac.md` — the task's acceptance criteria, numbered, copied verbatim from the task's brief
  (or `$2`, or GitHub issue `#$1` via `gh issue view`).
- `manifest.md` — the base tree, the snapshot tree, and every changed file grouped into
  review **areas**. Group by purpose (production code, tests, fixtures/golden data,
  docs, `action.yml` + CI/config/agent files). Prefer ≤ ~1500 changed lines
  per area; split a larger group.
- `ledger.md` — one table, one row per finding:
  `id | area | file:line | severity | failure scenario | status | resolution`.
  Status is one of `open`, `fixed`, `waived`, `rejected`. A `waived` row records who
  accepted it and why; a `rejected` row records why the verifier rejected it. Below the
  table, a `## Rounds` section logs each round (snapshot tree, counts, next step).

Snapshot the working tree without committing (Git Bash; the real index is untouched):

```bash
mkdir -p .review/$1
BASE=$(git rev-parse "$(git merge-base master HEAD)^{tree}")
SNAP=$(GIT_INDEX_FILE=.review/$1/.index sh -c 'git read-tree HEAD && git add -A && git write-tree' 2>/dev/null)
git diff --stat "$BASE" "$SNAP"
```

`git diff "$BASE" "$SNAP"` is the full branch diff, staged, unstaged and untracked included. Seeding the
temporary index from `HEAD` keeps tracked files that `.gitignore` also matches; a bare `git add -A` on an
empty index would drop them and show them as deleted.

## 1. Acceptance criteria against code

For each criterion in `ac.md`, confirm the **literal claim** against the code — the return
annotation, the sort call, the guard position, the single validation site, the actual file
contents. A same-named green test is not evidence. Record criterion → met / not met →
`file:line`. A criterion not met is a Blocker row in the ledger.

## 2. QA gates

Run `make qa`; record Pylint score, Black, mypy, coverage %, and every other target. A red
gate is a Blocker row.

## 3. Full review — one fresh reviewer per area, in parallel

Spawn one fresh-context subagent per area (Agent tool, `general-purpose`), all in one
message. Each prompt carries: the area's file list, the base and snapshot trees, `ac.md`,
the severity bar above, the current `ledger.md`, and the instruction to follow
`.github/agents/reviewer.agent.md` in **verification mode**. Each reviewer must:

- review every file in its area via `git diff "$BASE" "$SNAP" -- <files>` plus the
  surrounding code it needs;
- report **every** finding (no cap) as a ledger row candidate with a failure scenario;
- emit a coverage line per file — `path — reviewed, N findings` (`0` is a valid answer);
- not re-raise a `waived`, `rejected` or `fixed` ledger row unless it cites new evidence.

Reject a reviewer report that is missing a coverage line for any file in its area — re-run
that area.

## 4. Verify findings — independent, fresh context

Spawn one fresh-context verifier per area that has candidate Blocker/Important findings.
It reads the cited code and marks each candidate `CONFIRMED` (failure scenario holds on
the current snapshot) or `REJECTED` (with the reason). Append confirmed ones to the ledger
as `open`, rejected ones as `rejected`, Nits as `waived` with resolution `nit`.

## 5. Fix round

If the ledger has no `open` Blocker/Important rows, go to step 7.

Otherwise fix **all** open rows in one batch — the smallest change per row, no refactors
beyond the row's scope, no lowered thresholds, no inline disables. Add a test for every
row whose failure scenario is a code path. Re-run `make qa` until green. Mark each row
`fixed` with the `file:line` of the fix. Take a new snapshot `SNAP2` (same command as
step 0) and log the round.

If a row needs a decision only the user can make (a contract change, a scope question),
mark it `open`, stop the loop, and ask.

## 6. Delta review — fix diff only, fresh context

Spawn one fresh-context reviewer over `git diff "$SNAP" "$SNAP2"` plus the direct callers
of every changed symbol. Same rules as step 3; verify its candidates as in step 4. Any new
confirmed Blocker/Important row ⇒ back to step 5 with `SNAP=$SNAP2`.

**Round limit — 3 fix rounds.** After round 3, remaining open Important rows become
follow-up items listed in the verdict (they do not block); remaining open Blockers mean
`PR-READY: no`.

## 7. Stop condition and verdict

The loop converges when all hold at the latest snapshot:

- the last review (full or delta) produced zero new confirmed Blocker/Important rows;
- `make qa` is green on that snapshot;
- every criterion in `ac.md` is met with a `file:line`.

Print exactly one of:

- `PR-READY: yes` — then the criterion → `file:line` table, the `make qa` numbers, the
  ledger summary (fixed / waived / rejected counts), and any follow-up items.
- `PR-READY: no` — then the ordered list of open ledger rows: id, `file:line`, the failure
  scenario, the concrete change needed.

A later run of this command on the same task reads the ledger and starts at step 0's
resume point. If the ledger is converged, take a fresh snapshot: when it equals the last
logged one, re-run only steps 1–2 and print the verdict; when the tree changed since (a
human edited after convergence), run step 6 on that delta, then steps 1–2 — never a new
full review.
