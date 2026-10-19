---
description: Implement a task end to end, from its acceptance criteria to a PR-ready description.
argument-hint: <task-id or issue number> (e.g. 2) [path-or-URL to the brief, if not the issue]
---

You are driving a single implementation task to completion in `living-doc-generator-markdown`.
Follow these steps **in this exact order**. Do not skip or reorder them.

Task ID: `$1`
Brief source (optional override): `$2`

## 1. Read the task

- Locate task `$1` in its GitHub issue (`gh issue view`) or in the brief the owner hands over.
  If `$2` is given, read it there.
- Read the task's **prompt** and its **acceptance criteria** in full. Also read the
  linked GitHub issue if the task names one.
- Write the acceptance criteria out as a numbered checklist you will verify against code
  in step 5. Do not start work until this list is explicit.

## 2. Read every file the task references — before writing any code

- Open every spec, doc, config, and source file named in the task prompt, its "Spec refs"
  line, and its acceptance criteria. Follow one hop of cross-references (a spec section that
  points at another spec section).
- Read the existing code the change touches and the tests that already cover it, so the
  implementation matches repo patterns (`.github/copilot-instructions.md`,
  `.github/copilot-review-rules.md`).
- If the task is ambiguous after reading, stop and ask — do not guess.

## 3. Implement to the spec exactly

- Make the smallest change that satisfies the spec. Match existing structure, naming,
  logging style (lazy `%` formatting, no `print`), and import conventions.
- Add or update tests for every new or changed code path (success + failure). Use the
  `test-author` agent for the test surface.
- Do not change externally-visible contracts (`action.yml` inputs/`INPUT_*`, output keys,
  exit codes, contract-sensitive strings) unless the task explicitly calls for it.
- Describe what the change builds in the live docs (`README.md`, `DEVELOPER.md`) in this same
  change. The specification lives outside this repository, in the task's issue or brief.

## 4. Run the `make qa` loop until green

- Run `make qa` (format-check, lint, types, runtime-requirements, coverage — the same targets CI runs).
- Fix every failure and re-run. Repeat until `make qa` exits clean:
  Pylint ≥ 9.5, Black clean, mypy clean, `pytest --cov-fail-under=80` passing.
- Do not lower a threshold, add an inline lint disable, or `# type: ignore` to get past a
  gate unless the repo documents that exception.

## 5. Verify each acceptance criterion against the actual code

For every criterion on your step 1 checklist, confirm the **literal claim** by reading the
code that now exists — **not** by checking that a same-named test is green.

- "returns a typed `X`" → read the function's real return annotation.
- "sorted descending" → read the actual sort call and its `reverse=`/key.
- "cache hit skips the API call" → confirm the guard/return precedes the call in the
  function body.
- "input is validated in one place" → confirm there is exactly one validation site.
- "file X exists / contains Y" → open X and confirm Y is literally present.

Record each criterion as met (with the `file:line` that proves it) or not met. If any
criterion is not met, return to step 3.

## 6. Write the PR description

Write a PR description (to `pr.md` in the repo root unless told otherwise) with exactly
these sections, per `CONTRIBUTING.md`:

- `## Overview` — what changed and why.
- `## Release Notes` — at least one real user-facing bullet (no `TBD`).
- `## Related` — use `Closes #<issue>` when the task is tied to a GitHub issue. If there is no issue,
  identify the owner-provided brief instead; do not invent an issue reference.

Include a short "Acceptance criteria" checklist mapping each criterion to the `file:line`
that satisfies it (from step 5).

## 7. Stop

Do not open the PR, push, or commit. Report: what changed, the `make qa` result, and the
acceptance-criteria verification table. Then stop.
