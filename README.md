# Living Doc Generator Markdown

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

A source-agnostic GitHub Action that will render the canonical Living Documentation dataset as plain Markdown files, meant to be committed alongside code and rendered by whatever already renders a repo's Markdown (GitHub, a wiki, a generic static site generator).

## Overview

> **The Living Documentation pipeline runs AI-free.** Every step — collect → normalize → generate — is deterministic tooling (Python, JSON Schema validation, Jinja2/Markdown templates) with no LLM call anywhere in that path. [`AbsaOSS/agentic-toolkit`](https://github.com/AbsaOSS/agentic-toolkit) can accelerate the upstream *authoring* of GitHub Issues and `.feature` files, but it is never a runtime dependency of this pipeline: a human writing the same input by hand is a fully supported, identical path.

`living-doc-generator-markdown` is the **Markdown generator** — the final stage of the Living Documentation pipeline. It consumes the canonical dataset produced by [`living-doc-toolkit`](https://github.com/AbsaOSS/living-doc-toolkit) and emits plain Markdown files. The output is intended to be committed next to the code it documents and rendered by any existing Markdown renderer, so no additional publishing infrastructure is required.

For where this generator sits in the wider pipeline, see the [Living Documentation architecture](https://github.com/AbsaOSS/living-doc/blob/master/docs/introduction/architecture.md) and [Choosing a Generator](https://github.com/AbsaOSS/living-doc/blob/master/docs/guides/choosing-a-generator.md).

## Status

**Not yet implemented.** This repository is scaffolding only — there is no `action.yml`, source, or `DEVELOPER.md` yet. The generator is built in **Phase 4** of the roadmap, scaffolded from the canonical action-repo conventions established in Phase 0: see [Roadmap → Phase 4 — Build `generator-markdown` against the same canonical contract](https://github.com/AbsaOSS/living-doc/blob/master/docs/specs/roadmap.md#phase-4--build-generator-markdown-against-the-same-canonical-contract).

Treat any inputs/outputs described elsewhere as directional, not authoritative, until Phase 4 lands.

## Contribution Guidelines

Contributions are welcome. See [CONTRIBUTING.md](./CONTRIBUTING.md) for the bug-report, feature-request, branch-naming, and PR conventions.

### License Information

Licensed under the Apache License 2.0 — see [LICENSE](./LICENSE).

### Contact or Support Information

Maintained by [ABSA Group Limited](https://github.com/AbsaOSS). Open a [GitHub Issue](https://github.com/AbsaOSS/living-doc-generator-markdown/issues) for questions, bug reports, or feature requests.
