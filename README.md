# Living Doc Generator Markdown

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

A source-agnostic GitHub Action that renders the canonical Living Documentation dataset as plain Markdown files, meant to be committed alongside code and rendered by whatever already renders a repo's Markdown (GitHub, a wiki, a generic static site generator).

## Overview

> **The Living Documentation pipeline runs AI-free.** Every step — collect → normalize → generate — is deterministic tooling (Python, JSON Schema validation, Jinja2/Markdown templates) with no LLM call anywhere in that path. The agentic layer in [`living-doc` `agentic/`](https://github.com/AbsaOSS/living-doc/tree/master/agentic) can accelerate the upstream *authoring* of GitHub Issues and `.feature` files, but it is never a runtime dependency of this pipeline: a human writing the same input by hand is a fully supported, identical path.

`living-doc-generator-markdown` is the **Markdown generator** — the final stage of the Living Documentation pipeline. It consumes the canonical dataset produced by [`living-doc-toolkit`](https://github.com/AbsaOSS/living-doc-toolkit) and emits plain Markdown files. The output is intended to be committed next to the code it documents and rendered by any existing Markdown renderer, so no additional publishing infrastructure is required.

For where this generator sits in the wider pipeline, see the [Living Documentation architecture](https://github.com/AbsaOSS/living-doc/blob/master/docs/introduction/architecture.md) and [Choosing a Generator](https://github.com/AbsaOSS/living-doc/blob/master/docs/guides/choosing-a-generator.md).

## Status

**Renders all three document types from the `living-doc-utilities` 0.8.0 contracts, from the files `living-doc-toolkit` writes; `living-doc-toolkit` has no release yet.** [`action.yml`](./action.yml) reads one [`living-doc-toolkit`](https://github.com/AbsaOSS/living-doc-toolkit) output, renders it as one Markdown document by the view the input declares (`inner` or `release`), and writes the document and a run report into `output-path`. It runs in a venv of its own, built from the Python on `PATH` (3.10 or later).

`source-path` is the one `living-doc-toolkit` output its document type renders, read through the [`living-doc-utilities`](https://github.com/AbsaOSS/living-doc-utilities) contracts:

| `document-type` | `source-path` | Written by the `living-doc-toolkit` command | Title without `document-title` |
|---|---|---|---|
| `technical-project` | `generator-ready.json` | `normalize-docs` | the input's `document.title`, else `Technical project` |
| `ui-test-catalog` | `ui-test-catalog.json` | `normalize-tests` | `UI test catalog` |
| `coverage-matrix` | `coverage-matrix.json` | `coverage-matrix` | `Coverage matrix` |

`living-doc-toolkit`'s unreleased `master` writes these files in their contracts' format. [DEVELOPER.md § Local Integration Run](DEVELOPER.md#local-integration-run) renders all three from one `living-doc-toolkit` run's files, outside any workflow; [§ Debug run](DEVELOPER.md#debug-run) writes one from the `living-doc-utilities` samples.

### Usage

```yaml
- uses: actions/setup-python@v7
  with:
    python-version: '3.12'

- name: Generate Markdown
  id: markdown
  uses: AbsaOSS/living-doc-generator-markdown@<commit-sha>  # no release is tagged yet
  with:
    document-type: technical-project   # required: technical-project, ui-test-catalog or coverage-matrix
    source-path: generator-ready.json  # required: the document type's input file
    output-path: docs/generated        # optional: a directory; default ./output/generator-markdown
    document-title: Payments service   # optional: the document's title
    verbose-logging: 'false'           # optional: 'true' for DEBUG logs

- run: ls "${{ steps.markdown.outputs.output-path }}"
```

| Output | Value |
|---|---|
| `output-path` | the `output-path` directory, resolved to an absolute path |

Each run writes two files into `output-path`, named by its document type, and leaves every other file there as it is:

| File | Holds |
|---|---|
| `<document-type>.md` | the document, e.g. `technical-project.md` |
| `<document-type>.run-report.json` | the input's contract and producer, its record counts (equal to its `metadata.stats.cardinality`), and the render manifest: the entity ids, acceptance criteria, aspects, badges and scenarios the document shows, and what was not loaded |

- The title is `document-title` when it is not empty; otherwise the default in the table above.
- The inner view shows everything the input holds, and what a collector could not load from it; the release view leaves out the fields [`living-doc-utilities`' rendering rules](https://github.com/AbsaOSS/living-doc-utilities/blob/master/docs/contracts/rendering.md#fields-by-view) mark inner-only. The view is the input's own `document.view`.
- A run that wrote both files exits 0 and sets `output-path`. Every failure is one line and exit code 1:
  - a missing `document-type` or `source-path`, or an unknown `document-type`, names the input;
  - a `source-path` that is missing, not a regular file, unreadable, or not JSON it can load, or a file its contract rejects, names `source-path`;
  - a collector output (`doc-source`, `doc-entities`, `ui-tests`) names the `living-doc-toolkit` command that writes the document type's input; another document type's file names its `document-type`;
  - an input written by another `living-doc-utilities` version that declares a contract version 0.8.0 does not ship is `INVALID_CONTRACT_ID`, with the hint to align the pins;
  - a template that reads a key its model lacks is `TEMPLATE_KEY_MISSING`, never an empty section;
  - an `output-path` that cannot be written, or that holds a line break, names `output-path`.

## Developer Guide

Setup, quality gates, a debug run, the action's venv rules and what CI runs: [DEVELOPER.md](./DEVELOPER.md). A run of all three document types over given `living-doc-toolkit` outputs, outside any workflow, is a development and operator-check affordance, not a second supported deployment target: [Local Integration Run](DEVELOPER.md#local-integration-run).

## Contribution Guidelines

Contributions are welcome. See [CONTRIBUTING.md](./CONTRIBUTING.md) for the bug-report, feature-request, branch-naming, and PR conventions.

### License Information

Licensed under the Apache License 2.0 — see [LICENSE](./LICENSE).

### Contact or Support Information

Maintained by [ABSA Group Limited](https://github.com/AbsaOSS). Open a [GitHub Issue](https://github.com/AbsaOSS/living-doc-generator-markdown/issues) for questions, bug reports, or feature requests.
