# Copilot Instructions — Living Documentation Generator for Markdown

This file tells a coding agent how to work in this repository. It describes this repo's
own layout, contract, and workflow; it is not shared with or copied from other repos.

**Section order** — keep the sections below in exactly this order:
Overview → Repo specifics → Coding guidelines → Inputs → Language and style →
Logging and string formatting → Docstrings and comments → Patterns → Testing →
Tooling and quality gates → Common pitfalls → Learned rules.

**House rules for this file**

- Must write every guidance bullet as a constraint led by one of `Must`, `Must not`, `Prefer`, `Avoid`.
- Must not put a colon after the leading keyword, and Must not use any other keyword style such as `Do`, `Should`, or a two-keyword `Do` / `Avoid` variant.
- Prefer bullet lists over paragraphs.
- Must end the file with a single trailing newline.

## Overview

`Living Documentation Generator for Markdown` is a composite GitHub Action that will render
one living-documentation input — `generator-ready.json`, `ui-test-catalog.json` or
`coverage-matrix.json`, in the contracts `living-doc-utilities` owns — as plain Markdown files.
It is the generate step of a living-documentation pipeline. Rendering is not implemented yet:
the action validates its inputs and fails. The specification lives outside this repository, in
each task's issue.

- Must treat execution as a GitHub Action on a GitHub-hosted runner as the supported path; a `python3 main.py` run is a development and debugging affordance only.
- Must read action inputs from `INPUT_*` environment variables and nowhere else.
- Must keep the whole generate pipeline AI-free — deterministic Python only, no LLM call anywhere in that path.
- Must keep environment access at the module boundary — `generator_markdown/action_inputs.py` — and Must keep any other module free of environment reads; `living-doc-utilities`' `setup_logging()`, called from `main.py`, reads `INPUT_VERBOSE_LOGGING` and `RUNNER_DEBUG` itself.

## Repo specifics

Module map — `main.py` at the root plus one package, `generator_markdown/`:

| Path | Responsibility |
|---|---|
| `main.py` | Entry point — `run()`; sets up logging, validates the inputs through `ActionInputs.from_environment()`, reads the input file through `read_source()`, then fails with `RENDERING_NOT_IMPLEMENTED_MESSAGE`; maps every failure to exit code `1` |
| `generator_markdown/action_inputs.py` | Input layer — `DocumentType` (the three document types), `ActionInputs.from_environment()` reads every `INPUT_*` but `INPUT_VERBOSE_LOGGING` via `living_doc_utilities.github.utils.get_action_input` and raises `ActionInputError` with a one-line message |
| `generator_markdown/source_reader.py` | Input file reader — `read_source()` reads `source-path` with `living_doc_utilities.contracts.io.read_artifact` as the one contract its document type renders (`CONTRACT_NAMES`) and returns the typed model; every failure is a `SourceInputError` with a one-line message naming `source-path` (`TOOLKIT_COMMANDS` for a collector output) |
| `action.yml` | Composite action — the venv step (Python check, venv under `$RUNNER_TEMP`, install, import check) and the run step (`-E main.py`, every input in `env:`) |
| `tools/check_runtime_requirements.py` | `make runtime-requirements` — the deny list that keeps `requirements.txt` runtime-only |
| `tools/write_sample_inputs.py` | Writes `living-doc-utilities`' full sample of each named contract into a directory — the integration jobs' inputs and a debug run's |

- Must treat `main.py` function `run()` as the entry point — its step order is `setup_logging()` → log `"Liv-Doc generator for Markdown - starting."` → `ActionInputs.from_environment()`, logging an `ActionInputError` and `sys.exit(1)` → log the valid inputs → `read_source()`, logging a `SourceInputError` and `sys.exit(1)` → log ``"Liv-Doc generator for Markdown - input read: `<schema_version>`."`` → log the input's producer at DEBUG → log `RENDERING_NOT_IMPLEMENTED_MESSAGE` → `sys.exit(1)`.
- Must keep exactly one error line per failed run, since `tests/test_main.py` asserts there is one.

Inputs — `INPUT_*` environment variables, parsed only in `ActionInputs` but `verbose-logging` (the first four named as `living-doc-generator-pdf` declares them, `verbose-logging` as `living-doc-collector-gh` does):

| Input | Env var | Required | Notes |
|---|---|---|---|
| `document-type` | `INPUT_DOCUMENT_TYPE` | yes | `technical-project`, `ui-test-catalog` or `coverage-matrix` (`DocumentType`) |
| `source-path` | `INPUT_SOURCE_PATH` | yes | the input JSON file — `generator-ready`, `ui-test-catalog` or `coverage-matrix` by document type; read by `read_source()` |
| `output-path` | `INPUT_OUTPUT_PATH` | no | an output directory, default `./output/generator-markdown` (`DEFAULT_OUTPUT_PATH`); empty means the default; resolved to an absolute path |
| `document-title` | `INPUT_DOCUMENT_TITLE` | no | default empty |
| `verbose-logging` | `INPUT_VERBOSE_LOGGING` | no | default `'false'`; `true`, in any case, gives DEBUG logs; read by `living_doc_utilities.logging_config.setup_logging()`, not by `ActionInputs` |

Contract-sensitive outputs:

- Must keep the Action output key `output-path` stable — `action.yml` declares it from the run step `liv-doc-generator`; the action does not set it yet, as no run succeeds.
- Must keep the input error messages stable — `` Input `document-type` is required; valid types: technical-project, ui-test-catalog, coverage-matrix. ``, `` Input `document-type` is '<value>', not a valid type; valid types: … ``, `` Input `source-path` is required: the path to the input JSON file. `` — tests assert exact text.
- Must keep the `SourceInputError` messages stable — each starts `` Input `source-path` is '<value>' ``; a collector output names `` the `living-doc-toolkit` command `normalize-docs` `` (`normalize-tests`, `coverage-matrix`) and another document type's file `` which document type `<type>` renders `` — `tests/generator_markdown/test_source_reader.py` asserts exact text.
- Must keep `RENDERING_NOT_IMPLEMENTED_MESSAGE` (`Rendering is not implemented yet: living-doc-generator-markdown validated its inputs and wrote no document.`) until rendering replaces it.
- Must keep every `action.yml` failure to one `::error::` line — `tests/test_action_yml.py` runs the venv step and asserts it.
- Must keep exit-code behaviour stable — `1` on every failure; no run exits `0` yet. There is no `2`–`5` taxonomy in this repo.
- Must keep the `"Liv-Doc generator for Markdown - ..."` log strings stable — tests assert on them.

## Coding guidelines

- Must keep changes small and scoped to the task.
- Prefer explicit code over clever constructs.
- Must keep externally visible behaviour stable unless the task is an intentional contract change.
- Must not change existing log texts or error messages without a stated reason.
- Prefer pure functions for reading and rendering logic, and Avoid reading the environment outside `generator_markdown/action_inputs.py` (`setup_logging()` excepted).

## Inputs

- Must read every input through `ActionInputs.from_environment()` but `verbose-logging`, which `setup_logging()` reads, and Must not call `get_action_input` or `os.getenv("INPUT_...")` from any other module.
- Must centralise parsing, defaulting, and validation in `ActionInputs`, and Must raise `ActionInputError` with a one-line message that names the input.
- Avoid duplicating input validation across modules.
- Must keep `document-type`, `source-path`, `output-path` and `document-title` identical to `living-doc-generator-pdf`'s, so a pipeline can switch generators, and `verbose-logging` identical to `living-doc-collector-gh`'s.

## Language and style

- Must target Python 3.10+ (the ecosystem floor; the action runs on whatever Python ≥ 3.10 is on the caller's `PATH`, and the CI matrix covers 3.10–3.14).
- Must add type hints for new public functions and classes.
- Must keep imports at module top — no imports inside functions or methods.
- Must guard any 3.11+ standard-library use behind a `sys.version_info` fallback.
- Must not disable a linter rule inline unless this file records the exception under Learned rules.

## Logging and string formatting

- Must use `logging`, never `print`.
- Must use lazy `%` formatting in logging calls — `logger.info("msg %s", value)`.
- Must not use f-strings inside logging calls.
- Prefer the clearest formatting when constructing exception and failure messages, and Must keep contract-sensitive strings stable.

## Docstrings and comments

- Must match the existing module docstring style — a short summary of what the module contains.
- Prefer a one-line docstring summary for functions, with `@param` / `@return` / `@raise` lines where they add information, matching the surrounding code.
- Prefer self-explanatory code, and Prefer comments only for intent, edge cases, and the "why".
- Avoid tutorial-style prose or long examples in docstrings.

## Patterns

- Prefer leaf modules raising a typed exception (`ActionInputError`) over logging and exiting themselves.
- Must let `main.run()` be the only place that translates a failure into an Action-failure exit code.
- Must keep the filesystem boundary — reading the input, writing into `output-path` — explicit and mockable.
- Must read an input artifact only with `living_doc_utilities.contracts.io.read_artifact`, and Must not add a local contract model or a committed schema copy.

## Testing

- Must use `pytest` with `pytest-mock` (`mocker`), and Must not use `unittest`.
- Must keep tests under `tests/`, mirroring the package layout — `tests/generator_markdown/`, plus `tests/test_main.py`, `tests/test_action_yml.py`, `tests/test_contract_checks.py`, `tests/test_runtime_requirements.py` and `tests/test_write_sample_inputs.py`.
- Must test behaviour — return values, raised exceptions, log messages, exit codes.
- Must set `INPUT_*` environment variables with `monkeypatch.setenv` in unit tests; `tests/conftest.py` clears every inherited `INPUT_*` first.
- Must not call external services or the GitHub API in unit tests.
- Prefer shared fixtures in `tests/conftest.py` (`valid_inputs`, `write_sample`).
- Must treat the contracts as owned by `living-doc-utilities` — imported, never vendored: no committed `*-schema.json`, no local contract model.

## Tooling and quality gates

- Must run `make qa` before finishing a code change — it runs `format-check` → `lint` → `types` → `no-vendored-schemas` → `runtime-requirements` → `coverage` and fails on the first failing gate.
- Must use the individual targets while iterating — `make format`, `make format-check`, `make lint`, `make types`, `make no-vendored-schemas`, `make runtime-requirements`, `make test`, `make coverage`.
- Must keep `make lint` clean — it runs ruff (`E` / `F` / `I` / `B` over tracked `*.py`, config in `pyproject.toml`) then Pylint, and Pylint must score 9.5 or higher.
- Must keep `make format-check` (Black, line length 120, config in `pyproject.toml`) clean, and Prefer `make format` (ruff autofix + Black) to fix import order and formatting in one step.
- Must keep `make types` (mypy, config in `pyproject.toml`) clean, and Prefer fixing types over adding ignores.
- Must keep `make coverage` (pytest, `--cov-fail-under=80`) passing.
- Must expect `.github/workflows/test.yml` to call the same `make` targets, so local and CI never drift.

## Common pitfalls

- Must verify a new dependency supports Python 3.10 before adding it, and Must keep `requirements.txt` and `action.yml` in step when inputs or dependencies change. Must put a test, lint or type pin in `requirements-dev.txt`, never in `requirements.txt`, which the action installs on every run.
- Must add a new input to `action.yml`'s inputs, to the run step's `env:` and to `ActionInputs` together (`verbose-logging` excepted: `setup_logging()` reads it) — under `-E` the run step's `env:` is the only way an input reaches `main.py`.
- Must remove unused imports and variables in the same change, and Avoid leaving dead code.
- Avoid changing externally visible strings, the `output-path` key, the default output directory, or exit codes unless the task calls for it.

## Learned rules

- Must keep the `ActionInputError` and `SourceInputError` messages and `RENDERING_NOT_IMPLEMENTED_MESSAGE` stable — `tests/generator_markdown/test_action_inputs.py`, `tests/generator_markdown/test_source_reader.py` and `tests/test_main.py` assert exact strings and `sys.exit(1)`.
- Must not introduce a `2`–`5` exit-code taxonomy; this action reports every failure as `1`.
- Must keep a user-supplied value in an error message on one line (`!r`), since a run fails with exactly one error line.
