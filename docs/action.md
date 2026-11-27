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
  - The document prints no view: its file name carries it ([Files](#files)).
- Every document lists the entities of each type in ascending order of their ids' numbers
  - The numbers compare one by one: `US-2` before `US-10`, `FEAT-2024-3` before `FEAT-2024-10`.
  - An id without a number comes after the numbered ones; ids of equal numbers keep the input's order.
  - A technical project's acceptance criteria keep their authored order.
- A coverage matrix opens with the matrix's totals, then one table per entity type
  - A row per entity: its ID linked to its chapter, its title, state, coverage and counts.
  - The figures are the input's own summaries, never recomputed.
- A technical project opens with one table per entity type, in place of a contents list
  - A row per entity: its ID linked to its chapter, its title and state, then its counts.
  - A User Story or a Functionality counts its acceptance criteria by state; the release view, which holds no
    `in_review` or `planned` criterion, shows only the `active` and `deprecated` counts.
  - A Feature counts the Functionalities its chapter lists.
  - The counts are of the input's records, never of coverage.
- A technical project shows each entity's acceptance criteria as one table: ID, version, state and description
  - A planned criterion without a version shows `backlog`; a deprecated one shows its removal target after its state.
  - A criterion's aspects, keyword values, rationale, and its own preconditions and not-in-scope items follow the
    table, under the criterion's ID.
- A UI test catalog opens with its contents, then shows the entities its tests link, then the tests by feature file
  - The layout is the one agreed on [AbsaOSS/living-doc#155](https://github.com/AbsaOSS/living-doc/issues/155#issuecomment-7158222252).
  - *User Stories*, then *Functionalities*: a chapter per entity a test links, with a table of a row per criterion
    and test: the criterion's ID and state, the test linked to its chapter, the test's state, aspects and tags.
  - *User Story tests*, then *Functionality tests*: a chapter per feature file, in file-name order, naming the
    entities its tests link, its source and its `Background:`, then a chapter per test in line order.
  - A test's chapter shows its status, rule, the criteria it covers, its examples, its tags but the `@AC:` ones, its
    line at the source, then its steps as written in a `gherkin` block; a rule's `Background:` shows once, before
    its first test.
  - A file goes under *User Story tests* when a test links a User Story, otherwise under *Functionality tests*.
  - A test title that repeats among the tests gets its file's name, so every heading and link is unique.
- A UI test catalog decides from the links its input holds, after the release view dropped the `planned` and
  `in_review` ones
  - A feature file none of whose tests links a criterion is in no chapter; only the inner view lists it, with its
    test count, under *Not linked to an entity*.
  - Only the inner view marks a test that links no criterion, with the badge `NO AC`.
- A UI test catalog marks a scenario tagged `@skip` with the badge `SKIPPED`
  - Its criteria show under *Skipped, not counted* in place of *Covers*: the coverage matrix counts none of them.
  - Only the scenario's own tag marks it, exactly `@skip`; its tags still list it, in both views.

The three document types, one step each, over the files one `living-doc-toolkit` run wrote:

```yaml
- uses: AbsaOSS/living-doc-generator-markdown@v0.2.0
  with:
    document-type: technical-project
    source-path: output/generator-ready.json
- uses: AbsaOSS/living-doc-generator-markdown@v0.2.0
  with:
    document-type: ui-test-catalog
    source-path: output/ui-test-catalog.json
- uses: AbsaOSS/living-doc-generator-markdown@v0.2.0
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
| `release-version` | no | `''` | The release a release-view input describes, as `X.Y.Z` or `vX.Y.Z`, not validated; it names the files ([Files](#files)). Required for a release-view input, ignored for an inner-view one |
| `verbose-logging` | no | `false` | `true`, in any case, logs at DEBUG; a re-run with debug logging (`RUNNER_DEBUG=1`) does the same without it |

## Outputs

| Output | Meaning |
|---|---|
| `output-path` | The `output-path` directory, resolved to an absolute path; set once both files are written |

- A later step reads it as `${{ steps.<id>.outputs.output-path }}`, with the generator step's `id`
- A failed run sets no `output-path` ([Errors](#errors))

## Files

Each run writes two files into `output-path`, named by its document type and its view, and leaves every other file
there as it is:

<!-- over limit: one row per file; the run report's row lists what it holds -->
| File | Holds |
|---|---|
| `<document-type>-<view>.md` | the document, e.g. `technical-project-inner.md` or `technical-project-release-v1.2.0.md` |
| `<document-type>-<view>.run-report.json` | the input's contract and producer, its record counts (equal to its `metadata.stats.cardinality`), and the render manifest: the entity ids, acceptance criteria, aspects, badges and scenarios the document shows, and what was not loaded |

- `<view>` is `inner` for an inner-view input, and `release-vX.Y.Z` for a release-view one, from `release-version`
  - `1.2.0` and `v1.2.0` both give `release-v1.2.0`; the value is not validated.
  - An inner run and a release run can write into one directory without overwriting each other.
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
| input | a release-view input without `release-version` | one line naming `release-version` |
| render | a template reads a key its model lacks | `TEMPLATE_KEY_MISSING`, never an empty section |
| output | `output-path` cannot be written | one line naming `output-path` |
| output | the `output-path` output cannot be set | one line naming it |

- The inputs are checked in `action.yml` order, `document-type` first; `release-version` once the input's view is
  read
- The codes, and the fixed order a consumer checks an input in, are `living-doc-utilities`':
  [codes](https://github.com/AbsaOSS/living-doc-utilities/blob/master/docs/contracts/errors.md#codes),
  [R5](https://github.com/AbsaOSS/living-doc-utilities/blob/master/docs/contracts.md#rules)
