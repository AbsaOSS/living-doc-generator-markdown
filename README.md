# Living Doc Generator Markdown

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

A source-agnostic GitHub Action that will render the canonical Living Documentation dataset as plain Markdown files, meant to be committed alongside code and rendered by whatever already renders a repo's Markdown (GitHub, a wiki, a generic static site generator).

## Overview

> **The Living Documentation pipeline runs AI-free.** Every step — collect → normalize → generate — is deterministic tooling (Python, JSON Schema validation, Jinja2/Markdown templates) with no LLM call anywhere in that path. The agentic layer in [`living-doc` `agentic/`](https://github.com/AbsaOSS/living-doc/tree/master/agentic) can accelerate the upstream *authoring* of GitHub Issues and `.feature` files, but it is never a runtime dependency of this pipeline: a human writing the same input by hand is a fully supported, identical path.

`living-doc-generator-markdown` is the **Markdown generator** — the final stage of the Living Documentation pipeline. It consumes the canonical dataset produced by [`living-doc-toolkit`](https://github.com/AbsaOSS/living-doc-toolkit) and emits plain Markdown files. The output is intended to be committed next to the code it documents and rendered by any existing Markdown renderer, so no additional publishing infrastructure is required.

For where this generator sits in the wider pipeline, see the [Living Documentation architecture](https://github.com/AbsaOSS/living-doc/blob/master/docs/introduction/architecture.md) and [Choosing a Generator](https://github.com/AbsaOSS/living-doc/blob/master/docs/guides/choosing-a-generator.md).

## Status

**In development: the action reads its input and does not render yet.** [`action.yml`](./action.yml) takes five inputs — `document-type` (`technical-project`, `ui-test-catalog` or `coverage-matrix`), `source-path`, `output-path` (a directory, default `./output/generator-markdown`), `document-title` and `verbose-logging` (`true` for DEBUG logs, default `false`) — and runs in a venv of its own, built from the Python on `PATH`.

`source-path` is the one [`living-doc-toolkit`](https://github.com/AbsaOSS/living-doc-toolkit) output its document type renders, read through the [`living-doc-utilities`](https://github.com/AbsaOSS/living-doc-utilities) contracts:

| `document-type` | `source-path` | Written by the `living-doc-toolkit` command (next release) |
|---|---|---|
| `technical-project` | `generator-ready.json` | `normalize-docs` |
| `ui-test-catalog` | `ui-test-catalog.json` | `normalize-tests` |
| `coverage-matrix` | `coverage-matrix.json` | `coverage-matrix` |

Today's `living-doc-toolkit` writes none of these files yet; [DEVELOPER.md § Debug run](DEVELOPER.md#debug-run) writes one from the `living-doc-utilities` samples.

- A missing `document-type` or `source-path`, or an unknown `document-type`, fails the run with one line naming the input.
- A `source-path` that is missing, unreadable or not JSON, or a file its contract rejects, fails the run with one line naming `source-path`.
- A collector output (`doc-source`, `doc-entities`, `ui-tests`) fails with one line naming the `living-doc-toolkit` command that writes the document type's input; another document type's file fails naming its `document-type`.
- A valid input fails the run too, with `Rendering is not implemented yet: …`, so no pipeline mistakes this version for one that wrote a document.

Do not add this action to a pipeline yet.

## Developer Guide

Setup, quality gates, a debug run and the action's venv rules: [DEVELOPER.md](./DEVELOPER.md).

## Contribution Guidelines

Contributions are welcome. See [CONTRIBUTING.md](./CONTRIBUTING.md) for the bug-report, feature-request, branch-naming, and PR conventions.

### License Information

Licensed under the Apache License 2.0 — see [LICENSE](./LICENSE).

### Contact or Support Information

Maintained by [ABSA Group Limited](https://github.com/AbsaOSS). Open a [GitHub Issue](https://github.com/AbsaOSS/living-doc-generator-markdown/issues) for questions, bug reports, or feature requests.
