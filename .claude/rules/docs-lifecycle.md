# Rule: docs lifecycle — specs shrink as code ships

`SPEC.md` describes what does **not** exist yet. Once a section is implemented, that
section stops being a spec and becomes a fact about the codebase — so it belongs in the
live docs, not in `SPEC.md`.

## The rule

When a PR implements a `SPEC.md` section, that same PR must:

1. **Delete** the implemented content from `SPEC.md` (the whole section, or the specific
   subsections that are now shipped).
2. **Add** the equivalent, "what actually exists" description to the live docs:
   - `README.md` for the action's inputs, outputs, output layout and run-level errors;
   - `DEVELOPER.md` for local-dev workflow, the gates and the action's venv rules.

This is a **move**, not a copy. After the PR, the information exists in exactly one place —
the live docs — and `SPEC.md` is smaller. `SPEC.md` trends toward empty as the rendering ships.

## What "move" means

- Do not leave the section in `SPEC.md` with a "✅ implemented" marker. Remove it.
- Do not duplicate the rule, flow or table in both `SPEC.md` and a live doc. One home.
- If only part of a section shipped, split it: the shipped part moves to live docs, the
  unshipped part stays in `SPEC.md`.
- Cross-references that pointed at the moved `SPEC.md` section must be repointed to its new
  home in the same PR (keep `link-check` green).

## When SPEC.md is empty

When a spec document has no remaining unimplemented content, delete the file (or reduce it
to a one-line pointer to the live docs). A spec with nothing prospective in it is drift
waiting to happen.
