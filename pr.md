<!-- What problem does it solve or what feature does it add? -->
## Overview

The action now opens `source-path`. Each document type reads its one `living-doc-toolkit` output through `living-doc-utilities`' `read_artifact` and gets the typed contract model. A wrong file fails with one line that says what to run instead. There is still no rendering: a valid input is read, then the run fails as before.

- **The reader.** `generator_markdown/source_reader.py::read_source` maps each `document-type` to its contract (`technical-project` → `generator-ready`, `ui-test-catalog` → `ui-test-catalog`, `coverage-matrix` → `coverage-matrix`) and calls `read_artifact(source_path, expected=<name>)`. It reads no environment variables; `ActionInputs` stays the only module that does. Every failure is a `SourceInputError` with one line that starts with ``Input `source-path` is '<path>'``:
  - missing, a directory, unreadable, not UTF-8, not JSON: the generator's own line;
  - a collector output (`doc-source`, `doc-entities`, `ui-tests`): names the `living-doc-toolkit` command that writes this document type's input, `normalize-docs`, `normalize-tests` or `coverage-matrix` (the release names);
  - another document type's input: names the `document-type` that renders it;
  - `INVALID_CONTRACT_ID`, `SCHEMA_VALIDATION_FAILED`, an unknown contract name: `utilities`' own message, pin-alignment hint kept, collapsed onto one line (a model-level failure carries pydantic's multi-line report);
  - a version of the right contract that the installed `utilities` ships no schema for (e.g. `generator-ready-v9.9.9`): `read_artifact` raises a bare `FileNotFoundError` for the bundled schema here, so the reader tells it apart from a missing `source-path` and gives the pin hint.
- **`main.py`** reads the input after `ActionInputs`, logs ``input read: `<schema_version>` ``, then ends with `RENDERING_NOT_IMPLEMENTED_MESSAGE` and exit 1 as before.
- **No mirror of a contract.** `make no-vendored-schemas` (`living-doc-utilities`' `check_no_vendored_schemas`) is in `make qa` and in `Contract Checks`, and `tests/test_contract_checks.py` runs `find_vendored_schemas`. The repository has no schema file and no contract model.
- **`verbose-logging`.** A new input (`required: false`, default `'false'`, `collector-gh`'s description), passed as `INPUT_VERBOSE_LOGGING`. `setup_logging()` reads it; `ActionInputs` has no use for it.
- **Tests.** Inputs come from `full_sample()` written with `write_artifact` into `tmp_path` (new `write_sample` fixture). Broken files are built there too. There is one `isinstance` test per document type, and every rejection is asserted as exact text, per document type. 107 tests (60 before).
- **Integration jobs.** Each job writes `generator-ready.json` and `coverage-matrix.json` from `full_sample()` into `$RUNNER_TEMP/inputs`, in a throwaway venv built from `requirements.txt` and then deleted. It never touches the runner's interpreter, and no sample is committed. The 3.9 job writes them on 3.12 before it switches to 3.9. The replay runs `main.py` on the real file and expects the input read and the not-implemented line.
- **Workflow comments.** `test.yml` and `integration_test.yml` keep only the licence header. Each rule their comments stated is now stated once in the new `DEVELOPER.md` § CI, in § Action venv's "Why" form. Step and job names are unchanged.
- **`link-check.yml`.** A manual run sets `docs_changed=true`, as `test.yml`'s `detect` does, so lychee checks every page.
- **Docs and agent files.** `README.md` § Status: five inputs, the document type → input → `toolkit` command table, the new failures. `DEVELOPER.md`: the `no-vendored-schemas` gate, `INPUT_VERBOSE_LOGGING` and a sample-writing recipe in § Debug run, § CI. In `copilot-instructions.md`, `copilot-review-rules.md`, the board, `test-author.md` and `implement-task.md`, only the lines this change made false: the module map, the inputs, the asserted messages and the `make qa` targets.

<!-- Summarize the key changes for release notes. -->
## Release Notes
- The action reads `source-path` as the `living-doc-toolkit` output its `document-type` renders (`generator-ready`, `ui-test-catalog` or `coverage-matrix`), checked by `living-doc-utilities`; a valid input is read, then the run still fails with "Rendering is not implemented yet".
- A collector output given as `source-path` fails with one line naming the `living-doc-toolkit` command to run (`normalize-docs`, `normalize-tests`, `coverage-matrix`); another document type's file fails naming its `document-type`; a missing, unreadable, non-JSON or invalid file fails with one line naming `source-path`.
- New input `verbose-logging` (default `false`): `true` switches the log to DEBUG.

<!-- Add attached issue that this PR solves. -->
## Related
Closes #10

## Framework

Stays inside the frame. The change enforces two rows of `living-doc` `docs/introduction/principles.md` § The frame:

- **F4 Generators**, "a generator reads only toolkit outputs": a collector output is rejected, naming the `toolkit` command that writes the expected input.
- **F7 Pydantic models**, "no component mirrors a model or commits a schema copy": the input is read only through `read_artifact` into the `utilities` models, and `make no-vendored-schemas` guards against a committed schema.

## Contract gaps

Checked: `living-doc-utilities` 0.6.0 `docs/contracts/rendering.md` § Fields by view and `contracts.testing.shown_paths()` per view, against `GeneratorReadyResult`, `CoverageMatrixResult` and `UiTestCatalogResult`.

**No field the table names is missing from the three contracts.** Each row maps to a field:

- state badges: `state`, `state_origin`;
- `stub_reason`, `deprecated_at`, `deprecation_reason`, `removal_planned`;
- the planned target: `version`; the AC header: `canonical_header()`;
- AC- and entity-level `not_in_scope` and `preconditions`; `aspect`, `rationale`, `placeholder_values`;
- `source_ref.area_path`, `iteration_path`, `native_type`, `tracker_state`;
- `warnings[]`: `code`, `message`, `line_no`, `path` and `entity_id`. The link to the source line is the named entity's `source_ref.url` (a blob URL at a commit for a file source) plus `line_no`;
- `coverage-matrix`'s row and aspect statuses, both summaries and `planned_summary`;
- `ui-test-catalog` has no view-dependent field.

Two readings, neither a missing field:

- "Entity / AC `deprecated` state → deprecation date + reason": only an entity carries a date and a reason. The AC grammar has none, and `shown_paths` lists the entity's fields only.
- Outside the table, § Coverage labels a keyword criterion's breakdown with its `placeholder_values` key. `coverage-matrix`'s `AcCoverage` does not carry that key, and `component-checks.md` expects a generator to join contracts by criterion id. That needs a second input for the `coverage-matrix` document type, so it is left for the rendering work.

## Acceptance criteria

| # | Criterion | Where |
|---|---|---|
| 1 | Each document type reads with `read_artifact`, typed; no schema or model; check A in `make qa` and `Contract Checks` | `generator_markdown/source_reader.py:79`, `:103`; `Makefile:23`, `:40`; `.github/workflows/test.yml:129`; `tests/generator_markdown/test_source_reader.py:87`; `tests/test_contract_checks.py:23` |
| 2 | A collector output names `normalize-docs` / `normalize-tests` / `coverage-matrix` by document type | `generator_markdown/source_reader.py:113-118`; `tests/generator_markdown/test_source_reader.py:110` |
| 3 | Another `toolkit` output names its `document-type`; missing, unreadable, non-JSON, invalid `schema_version`, schema-invalid each fail with one line naming `source-path` | `generator_markdown/source_reader.py:81-100`, `:119-125`; `tests/generator_markdown/test_source_reader.py:137-297` |
| 4 | A valid input of each type is read, then `RENDERING_NOT_IMPLEMENTED_MESSAGE` and exit 1 | `main.py:63-70`; `tests/test_main.py:93`, `:156` |
| 5 | `verbose-logging` passed as `INPUT_VERBOSE_LOGGING`; `true` gives DEBUG; `README.md` and `DEVELOPER.md` list it | `action.yml:18-21`, `:67`; `tests/test_action_yml.py:114`, `:123`; `tests/test_main.py:180`, `:191`; `README.md:17`; `DEVELOPER.md:60`, `:65` |
| 6 | Integration jobs run on inputs built from `full_sample()` in the job; reuse, rebuild and the 3.9 rejection still shown | `.github/workflows/integration_test.yml:49-64`, `:113-114`, `:137`, `:204` |
| 7 | No rule-stating comment in `test.yml` / `integration_test.yml`; `DEVELOPER.md` states each once | `DEVELOPER.md:101` (§ CI) |
| 8 | A manual `link-check.yml` run runs lychee over every page | `.github/workflows/link-check.yml:54-57` |
| 9 | The PR body states the gap check | § Contract gaps above |
| 10 | `git grep -nE 'P35-\|DEC-[0-9]\|tasklist\|specs/\|Phase [0-9]' -- '*.md'` is empty | checked |
| 11 | `make qa` green | Pylint 10.00, mypy clean, 107 passed, coverage 98.59 % |
| 12 | `## Framework` in the PR body | § Framework above |

🤖 Generated with [Claude Code](https://claude.com/claude-code)
