# Living Doc Generator Markdown

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

## Purpose

A source-agnostic GitHub Action that renders one `living-doc-toolkit` output as one plain Markdown document, with a
run report. It is the generate step of a living-documentation pipeline, the final stage, after `living-doc-toolkit`.

## Contents

- [Overview](#overview)
- [Usage](#usage)
- [Inputs and outputs](#inputs-and-outputs)
- [Where next](#where-next)
- [Developer Guide](#developer-guide)
- [Contributing](#contributing)
- [License](#license)
- [Contact](#contact)

## Overview

- Three document types: a technical project, a UI test catalog and a coverage matrix, each from the one `living-doc-toolkit` output it reads → [Document types](docs/action.md#document-types)
- By view: a document shows what the view its input declares, `inner` or `release`, keeps → [Document types](docs/action.md#document-types)
- Two files per run, the document and its run report, into `output-path` → [Files](docs/action.md#files)
- Plain Markdown, meant to be committed next to the code it documents and rendered by whatever already renders the repository's Markdown (GitHub, a wiki, a generic static site generator), so no publishing infrastructure is needed
- Contract artifacts only: it reads its input through the `living-doc-utilities` contracts (`==0.8.1`) → [Contracts](https://github.com/AbsaOSS/living-doc-utilities/blob/master/docs/contracts.md)
- Pipeline-ready: collect → normalize → generate, this action being the generate step → [Architecture](https://github.com/AbsaOSS/living-doc/blob/master/docs/introduction/architecture.md), [Choose a generator](https://github.com/AbsaOSS/living-doc/blob/master/docs/guides/build-a-pipeline.md#choose-a-generator)
- GitHub Actions first: a step in a workflow is the supported way to run it; a local run is a development and operator-check aid, not a second deployment target → [Debug run](DEVELOPER.md#debug-run), [Local Integration Run](DEVELOPER.md#local-integration-run)
- AI-free: collect → normalize → generate is deterministic tooling, with no LLM call anywhere in that path → [AI-free Principle](CONTRIBUTING.md#ai-free-principle)
  - The tooling is Python, JSON Schema validation, and Jinja2 and Markdown templates.
  - The agentic layer in [`living-doc` `agentic/`](https://github.com/AbsaOSS/living-doc/tree/master/agentic) can speed up authoring GitHub Issues and `.feature` files.
  - It is never a runtime dependency: a human writing the same input by hand is a fully supported, identical path.

## Usage

One step that renders a technical project, after `actions/setup-python`
([Prerequisites](docs/action.md#prerequisites)):

```yaml
- name: Generate Markdown
  id: markdown
  uses: AbsaOSS/living-doc-generator-markdown@v0.1.0
  with:
    document-type: technical-project
    source-path: generator-ready.json
    output-path: docs/generated
    document-title: Payments service
```

The three document types: [Document types](docs/action.md#document-types). What lands in `output-path`, and how a
later step reads it: [Files](docs/action.md#files), [Outputs](docs/action.md#outputs).

## Inputs and outputs

Every input at a glance; required flags, defaults and errors are in the [action reference](docs/action.md#inputs).

- `document-type` (required): `technical-project`, `ui-test-catalog` or `coverage-matrix`
- `source-path` (required): the document type's input file
- `output-path`: the directory the document and its run report go into
- `document-title`: the document's title
- `verbose-logging`: debug logging

The one output, `output-path`, is that directory as an absolute path ([Outputs](docs/action.md#outputs)).

## Where next

| I want to… | Read |
|---|---|
| set every input, pick a document type, read the files and the output, handle an error | [Action reference](docs/action.md) |
| know which fields each view shows | [`living-doc-utilities` rendering rules](https://github.com/AbsaOSS/living-doc-utilities/blob/master/docs/contracts/rendering.md) |
| read the contracts and codes the generator implements | [`living-doc-utilities` contracts](https://github.com/AbsaOSS/living-doc-utilities/blob/master/docs/contracts.md) |
| see where the generator sits in the pipeline | [The frame](https://github.com/AbsaOSS/living-doc/blob/master/docs/introduction/principles.md#the-frame) |
| render one document from samples, or all three from a `living-doc-toolkit` run's files, outside any workflow | [Debug run](DEVELOPER.md#debug-run), [Local Integration Run](DEVELOPER.md#local-integration-run) |
| set up the repository, run the gates, read the design rules | [Developer guide](DEVELOPER.md) |
| contribute a change | [Contributing](CONTRIBUTING.md) |

## Developer Guide

Setup, the gates, the design rules, the local runs, the action's venv, CI and the page rules: [DEVELOPER.md](DEVELOPER.md).

## Contributing

Contributions are welcome. Bug reports, feature requests, the AI-free principle, and branch and pull request
conventions: [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Licensed under the Apache License 2.0; see [LICENSE](LICENSE).

## Contact

Maintained by [ABSA Group Limited](https://github.com/AbsaOSS). Open a
[GitHub Issue](https://github.com/AbsaOSS/living-doc-generator-markdown/issues) for questions, bug reports, or feature
requests.
