# Specification

## Purpose

Anyone who plans work on this repository reads this page. It holds only behaviour that is not built yet: the three
design rules the rendering is built to. A section leaves, into the live docs, in the change that builds it
([docs lifecycle](.claude/rules/docs-lifecycle.md)).

Read before: [README](README.md), which routes to everything that is built.

## Contents

- [One presentation module](#one-presentation-module)
- [Render manifest](#render-manifest)
- [Safe output](#safe-output)

## One presentation module

Not built. Which fields each view shows is defined in `living-doc-utilities`
([Rendering, Fields by view](https://github.com/AbsaOSS/living-doc-utilities/blob/v0.6.0/docs/contracts/rendering.md#fields-by-view));
this generator is the first to apply those rules.

- One module of this repository applies them. It maps an input and a view, `inner` or `release`, to a presentation
  model: what to show, the badges, the grouping.
- The templates only render that model. No template decides whether a field shows, which badge an entry gets or how
  entries group.
  - Why: a second generator would otherwise implement the same rules again, and the two would drift.
- The module stays here while this generator is its only consumer; `living-doc-utilities` changes nothing for it.
- When `living-doc-generator-pdf` renders these inputs again, the module moves into `living-doc-utilities`
  (`contracts.views.project(generator_ready, view)`), and both generators render what it returns.
- **The move is invisible from outside.** The action's inputs and outputs stay as they are, and the same input gives
  the same document and the same [render manifest](#render-manifest).
  - The golden tests prove it: the documents and render manifests rendered for both views are snapshot-tested before
    the move, and the move must leave both snapshots unchanged.

## Render manifest

Not built. Every run writes a render manifest into its run report, in `output-path` beside the document.

- The manifest lists, for the view the document was rendered in, the entity ids, the acceptance-criterion ids, the
  aspects and the badges the run rendered.
- When `living-doc-generator-pdf` returns, it writes the same manifest. The two generators render the same content
  exactly when their manifests are equal.
  - Why: two documents in two formats cannot be compared; two manifests can.

## Safe output

Not built. The Markdown is committed and rendered by GitHub and wikis, so an authored link or HTML fragment reaches
every reader.

- Every emitted field passes `living-doc-utilities` `authoring.url_policy`: a link is emitted only when `safe_href`
  keeps it ([URL policy](https://github.com/AbsaOSS/living-doc-utilities/blob/v0.6.0/docs/authoring/urls-and-html.md#url-policy)).
- No raw HTML passes through: authored text is emitted as text, never as markup.
- A hostile-content fixture tests both: rendering it yields no raw HTML and no link outside the URL policy.
