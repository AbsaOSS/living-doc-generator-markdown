# Action reference

## Purpose

This page is the action's full reference: what the runner needs, the document types, every input, the output, the
two files a run writes, and the errors.

Read before: [README](../README.md) · Next: [Developer guide](../DEVELOPER.md)

## Contents

- [Prerequisites](#prerequisites)
- [Document types](#document-types)
- [Inputs](#inputs)
- [Outputs](#outputs)
- [Files](#files)
- [Errors](#errors)

## Prerequisites

- Python 3.10 or later is on `PATH` as `python3`, or as `python` when there is no `python3`; the caller prepares it
  - Below 3.10, or with no Python, the step fails with one line before it creates anything ([Errors](#errors)).
- The action brings its own venv: it installs `requirements.txt` into `$RUNNER_TEMP/living-doc-generator-markdown-venv`
  and runs there
  - It never changes the caller's interpreter, `PATH` or environment, and writes nothing to `$GITHUB_ENV` or
    `$GITHUB_PATH`.
  - How it builds, checks and reuses the venv: [Action venv](../DEVELOPER.md#action-venv).
- The runner reaches a package index: each run installs the pinned requirements with `pip`
- It runs on Linux runners only: the venv's POSIX `bin/` layout is assumed
- The input file is on the runner, for example written by a `living-doc-toolkit` step earlier in the job
- The generator reads one local file and calls no API, so the action takes no token

Put `actions/setup-python` before the step:

```yaml
- uses: actions/setup-python@v7
  with:
    python-version: '3.12'
```

## Document types

One step renders one document type from the one `living-doc-toolkit` output it reads, through the
[`living-doc-utilities` contracts](https://github.com/AbsaOSS/living-doc-utilities/blob/master/docs/contracts.md).

| `document-type` | `source-path` | Written by the `living-doc-toolkit` command | Title without `document-title` |
|---|---|---|---|
| `technical-project` | `generator-ready.json` | `normalize-docs` | the input's `document.title`, else `Technical project` |
| `ui-test-catalog` | `ui-test-catalog.json` | `normalize-tests` | `UI test catalog` |
| `coverage-matrix` | `coverage-matrix.json` | `coverage-matrix` | `Coverage matrix` |

- The title is `document-title` when it is not empty; otherwise the default in the table above
- The view is the input's own `document.view`, `inner` or `release`; no action input sets it
  - The inner view shows everything the input holds, and what a collector could not load from it.
  - The release view leaves out the fields the
    [rendering rules](https://github.com/AbsaOSS/living-doc-utilities/blob/master/docs/contracts/rendering.md#fields-by-view)
    mark inner-only.

The three document types, one step each, over the files one `living-doc-toolkit` run wrote:

```yaml
- uses: AbsaOSS/living-doc-generator-markdown@v0.1.0
  with:
    document-type: technical-project
    source-path: output/generator-ready.json
- uses: AbsaOSS/living-doc-generator-markdown@v0.1.0
  with:
    document-type: ui-test-catalog
    source-path: output/ui-test-catalog.json
- uses: AbsaOSS/living-doc-generator-markdown@v0.1.0
  with:
    document-type: coverage-matrix
    source-path: output/coverage-matrix.json
    document-title: Payments coverage
```

## Inputs

Every input `action.yml` declares, in its order; a test keeps this table equal to it.

<!-- over limit: one row per input; the meanings are the one-line option-list entries the page rules ask for -->
| Input | Required | Default | Meaning |
|---|---|---|---|
| `document-type` | yes | — | The document to render: `technical-project`, `ui-test-catalog` or `coverage-matrix` ([Document types](#document-types)) |
| `source-path` | yes | — | Path to the document type's input file, the one `living-doc-toolkit` output it reads |
| `output-path` | no | `./output/generator-markdown` | The directory the run writes its two files into ([Files](#files)); an empty value is the default |
| `document-title` | no | `''` | The document's title; when empty, the document type's default ([Document types](#document-types)) |
| `verbose-logging` | no | `false` | `true`, in any case, logs at DEBUG; a re-run with debug logging (`RUNNER_DEBUG=1`) does the same without it |

## Outputs

| Output | Meaning |
|---|---|
| `output-path` | The `output-path` directory, resolved to an absolute path; set once both files are written |

- A later step reads it as `${{ steps.<id>.outputs.output-path }}`, with the generator step's `id`
- A failed run sets no `output-path` ([Errors](#errors))

## Files

Each run writes two files into `output-path`, named by its document type, and leaves every other file there as it is:

<!-- over limit: one row per file; the run report's row lists what it holds -->
| File | Holds |
|---|---|
| `<document-type>.md` | the document, e.g. `technical-project.md` |
| `<document-type>.run-report.json` | the input's contract and producer, its record counts (equal to its `metadata.stats.cardinality`), and the render manifest: the entity ids, acceptance criteria, aspects, badges and scenarios the document shows, and what was not loaded |

- The directory is created when it is missing

## Errors

A run that wrote both files and set the `output-path` output exits 0. The step fails at the first check that does not
pass, in this order. Every failure but a failed install is one line and exit code 1:

<!-- over limit: one row per failure; the last column is the line the step fails with -->
| Where | Situation | The step fails with |
|---|---|---|
| venv | no Python 3.10 or later on `PATH` | `::error::living-doc-generator-markdown needs Python >= 3.10 on PATH. Add actions/setup-python before this step.` |
| venv | `python -m venv` fails | `::error::living-doc-generator-markdown: '<python> -m venv' failed; install the venv module.` |
| venv | `pip install` of `requirements.txt` fails, for example with no package index | pip's own output and exit code |
| venv | the import check fails: the requirements did not land in the venv | one `::error::` line pointing at the runner's pip configuration, for a `target` or `prefix` setting |
| input | `document-type` or `source-path` is missing, or `document-type` is unknown | one line naming the input; for `document-type`, the valid types |
| input | `output-path` holds a line break | one line naming `output-path` |
| source | `source-path` does not exist, is not a regular file, is unreadable, or is not JSON it can load, or its contract rejects the file | one line naming `source-path` |
| source | a collector output (`doc-source`, `doc-entities`, `ui-tests`) | one line naming the `living-doc-toolkit` command that writes the document type's input |
| source | another document type's file | one line naming the `document-type` that renders it |
| source | an input written by another `living-doc-utilities` version, declaring a contract version the pinned one does not ship | `INVALID_CONTRACT_ID`, with the hint to align the pins |
| render | a template reads a key its model lacks | `TEMPLATE_KEY_MISSING`, never an empty section |
| output | `output-path` cannot be written | one line naming `output-path` |
| output | the `output-path` output cannot be set | one line naming it |

- The inputs are checked in `action.yml` order, `document-type` first
- The codes, and the fixed order a consumer checks an input in, are `living-doc-utilities`':
  [codes](https://github.com/AbsaOSS/living-doc-utilities/blob/master/docs/contracts/errors.md#codes),
  [R5](https://github.com/AbsaOSS/living-doc-utilities/blob/master/docs/contracts.md#rules)
