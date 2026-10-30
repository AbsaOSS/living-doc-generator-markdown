# Living Documentation Generator for Markdown: developer guide

## Purpose

Anyone who changes this repository reads this page. It covers setup, the quality gates, the design rules the
rendering keeps, a debug run, a local integration run over given `living-doc-toolkit` outputs, the rules the action's
venv follows, and what CI runs.

Read before: [README](README.md)

## Contents

- [Setup](#setup)
- [Gates](#gates)
- [Design rules](#design-rules)
- [Debug run](#debug-run)
- [Local Integration Run](#local-integration-run)
- [Action venv](#action-venv)
- [CI](#ci)

## Setup

1. Use Python 3.10 or later: `python3 --version`.
2. Create and activate a virtual environment: `python3 -m venv .venv`, then `source .venv/bin/activate`.
3. Run `make install`: `pip install -r requirements-dev.txt`, which pulls in `requirements.txt`.

| File | What it holds | Who installs it |
|---|---|---|
| `requirements.txt` | Runtime only: `living-doc-utilities` and `Jinja2`, the packages `main.py` and `generator_markdown/` import | `action.yml`, into its venv, on every run; `local-integration.sh`, into its own |
| `requirements-dev.txt` | `-r requirements.txt`, the gate and test tools, `PyYAML` for `tests/test_action_yml.py` and `markdown-it-py` for the rendering tests | `make install` and `test.yml` |

- The supported floor is 3.10, as `pyproject.toml` `requires-python` states; [CI](#ci) says which versions are tested.
- A test, lint or type tool in `requirements.txt` would download on every run of every caller; `make qa` fails on one.
- Dependabot covers both files from its single `pip` entry in `.github/dependabot.yml`.

## Gates

`make qa` runs `format-check`, `lint`, `types`, `no-vendored-schemas`, `runtime-requirements` and `coverage`, and
stops at the first failure. Run it before opening a pull request.

| Target | Runs | Gate |
|---|---|---|
| `make format` | ruff autofix, then Black, rewriting files | line length 120 |
| `make format-check` | Black in check mode | clean |
| `make lint` | ruff, then Pylint; Pylint skips `tests/` | Pylint ≥ 9.5 / 10 (`PYLINT_MIN`) |
| `make types` | mypy over the project; `tests/` is excluded | clean |
| `make no-vendored-schemas` | `living-doc-utilities`' `check_no_vendored_schemas` over git's index | no committed `*-schema.json` or `*.schema.json` outside a `tests/` directory |
| `make runtime-requirements` | `tools/check_runtime_requirements.py` | no test, lint or type tool in `requirements.txt` |
| `make test` | pytest over `tests/` | pass |
| `make coverage` | pytest with coverage; `tests/` is not measured | ≥ 80 % (`COV_MIN`) |

- `test.yml` calls the same targets; [CI](#ci) says which run where.
- Black, ruff and Pylint take their files from `git ls-files`, so a new file is checked once it is tracked.
- Black, ruff and mypy read their settings from `pyproject.toml`; Pylint reads `.pylintrc`. `make help` lists
  every target.

## Design rules

The rendering keeps three rules. Each is held by one module, and a test fails when it breaks.

| Rule | Module | Test |
|---|---|---|
| One presentation module maps an input model and its `document.view` to a presentation model of plain data; a template under `templates/<document-type>/` only renders it. Its later move into `living-doc-utilities` changes nothing a caller sees. | `generator_markdown/presentation.py` | `tests/generator_markdown/test_golden.py`, against `tests/fixtures/golden/` |
| Every run report carries the render manifest: per view, the entity ids, acceptance criteria, aspects and badges the document shows. | `generator_markdown/run_report.py`, from `presentation.py`'s `render_manifest()` | `tests/generator_markdown/test_run_report.py` |
| Every link passes `living_doc_utilities.authoring.url_policy.safe_href`, and every printed value is escaped, so no raw HTML, link, heading or list from an input reaches the Markdown. GitHub still links a bare address in authored text by itself, to the address as written. | `generator_markdown/presentation.py` for links, `generator_markdown/renderer.py` for escaping | `tests/generator_markdown/test_safe_output.py` |

- The presentation module imports only the `living-doc-utilities` contract models and returns frozen dataclasses: no
  Jinja type, no file access.
  - Why: a move must change neither its input nor its output, which the golden snapshots compare byte for byte.
- A link inside the document points to an anchor the presentation derives from an entity id, `[a-z0-9_-]` only; an
  entity's heading holds its id alone, so every renderer derives the same anchor. An id outside ASCII, or one whose
  anchor would be empty or another id's, shows unlinked, as an id the document does not hold does.
- After an intended change to the output, rewrite the snapshots with
  `UPDATE_GOLDEN=1 pytest tests/generator_markdown/test_golden.py`, and review their diff with the change.

## Debug run

```shell
export INPUT_DOCUMENT_TYPE=technical-project            # required: technical-project, ui-test-catalog or coverage-matrix
export INPUT_SOURCE_PATH=generator-ready.json           # required: the document type's input file
export INPUT_OUTPUT_PATH=./output/generator-markdown    # the default
export INPUT_DOCUMENT_TITLE='Payments service'          # optional: the document's title
export INPUT_VERBOSE_LOGGING=true                       # optional: DEBUG logs; default false
python3 main.py
```

- Each input is an `INPUT_<NAME>` variable, upper case with `_` for `-`, as `action.yml` passes it.
- `INPUT_VERBOSE_LOGGING=true`, in any case, switches the log to DEBUG, as `RUNNER_DEBUG=1` does;
  `living-doc-utilities`' `setup_logging()` reads both, not `ActionInputs`.
- Without `living-doc-toolkit`, write an input from `living-doc-utilities`' samples; `ui-test-catalog` and
  `coverage-matrix` give the other two document types':

  ```shell
  python3 tools/write_sample_inputs.py . generator-ready
  ```

- A run with a valid input writes `<document-type>.md` and `<document-type>.run-report.json` into `output-path` and
  exits 0. Without `GITHUB_OUTPUT`, as outside GitHub Actions, it sets no `output-path` output and logs that once.

## Local Integration Run

`local-integration.sh` renders the three document types from given `living-doc-toolkit` outputs, on the machine that
has them, outside any workflow. It renders each through `main.py` in a venv of its own, re-reads every input with
`read_artifact`, checks each document and its run report against it, and prints what ran and what came out. No
workflow runs it; like the [debug run](#debug-run), it is a development and operator-check affordance, not a second
supported deployment target.

- The usual inputs are the three files one `living-doc-toolkit` run wrote: its
  [Local Integration Run](https://github.com/AbsaOSS/living-doc-toolkit/blob/master/DEVELOPER.md#local-integration-run)
  says where they land. The script never derives another component's paths; you configure all three files.
- One `living-doc-toolkit` run writes one view. A release document needs its own `living-doc-toolkit` run with
  `VIEW=release`, into its own `OUT_DIR`, and then this script over that run's files, into another `OUT_DIR` of its
  own.
  - `normalize-tests` takes no view, so the catalog is `inner` in both runs and renders the same document.

### What You Prepare

The script checks the Python version, `git` and the three inputs, and nothing else of the environment. The rest is
yours:

- **Python ≥ 3.10**, with its `venv` module. The script uses `PYTHON` from `.env.local` when set, else `python3`, else
  `python` from `PATH`, the order `action.yml` uses.
  - On Git Bash for Windows, `python3` may be the Microsoft Store alias, which does not run: set `PYTHON=python`.
- **`git`** on `PATH`: the report's header names this repository's commit.
- **Network and pip configuration** that lets `pip install -r requirements.txt` succeed: `pip.conf`, `PIP_INDEX_URL`,
  `PIP_FIND_LINKS`, a proxy. The script leaves them as they are.
- **A POSIX shell**: bash 3.2 or later; Linux, macOS, or Git Bash on Windows.

No token: the generator reads local files and calls no API, so the script reads no credential.

- It unsets `GITHUB_TOKEN`, `GH_TOKEN`, `GH_ENTERPRISE_TOKEN`, `GITHUB_ENTERPRISE_TOKEN` and every inherited `INPUT_*`
  before it starts anything.
- `.env.local` is read as data, never sourced. A token left in it is ignored; the script reports its line by number,
  never its text.

### Configure It

```shell
cp .env.local.example .env.local      # .env.local is git-ignored
python3 tools/write_sample_inputs.py output/samples generator-ready ui-test-catalog coverage-matrix
```

As committed, the example renders the `living-doc-utilities` samples under `output/samples/`, which the second
command writes in the development venv ([Setup](#setup)); no sample is committed ([CI](#ci)).

| Key | Required | What it sets |
|---|---|---|
| `TECHNICAL_PROJECT_INPUT` | yes | `source-path` of `technical-project`: a `generator-ready` file, which `normalize-docs` writes |
| `UI_TEST_CATALOG_INPUT` | yes | `source-path` of `ui-test-catalog`: a `ui-test-catalog` file, which `normalize-tests` writes |
| `COVERAGE_MATRIX_INPUT` | yes | `source-path` of `coverage-matrix`: a `coverage-matrix` file, which `coverage-matrix` writes |
| `OUT_DIR` | no | the output root, default `./output` (git-ignored) |
| `PYTHON` | no | the interpreter the venv is built from |

- A relative path resolves against this repository's root; `~/` is the home directory.
- One `KEY=value` per line; a line starting with `#` is a comment, and values are taken literally.
- No key sets `document-title`: each document's title is the one a run without it gives ([README](README.md#status)).

### Run It

```shell
./local-integration.sh --check   # Python, git, the configuration and the three inputs; creates no venv, runs nothing
./local-integration.sh           # the run
```

A run, in order:

1. **Checks** what `--check` checks. A missing setting or input file, an input inside the directory the run clears,
   or a Python below 3.10 stops it with one line that names it.
2. **Builds its venv**, `.venv-local-integration/` (git-ignored), separate from the development `.venv`. It installs
   only `requirements.txt` (`pip install -r`), from the repository root: a runtime requirement missing from that file
   fails here, as on a runner.
   - It follows [Action venv](#action-venv): the same six variables unset, the same import check after the install,
     and `main.py` run with `-E`.
   - The venv is reused only when the same interpreter built it from the same `requirements.txt`.
3. **Prints what runs**: this repository's commit, the installed `living-doc-utilities` version, the Python version,
   the three inputs and the output directory. The commit is marked when tracked files differ from it.
4. **Renders `technical-project`, `ui-test-catalog`, then `coverage-matrix`**, each as its own `main.py` run with only
   `document-type`, `source-path` and `output-path`, into `$OUT_DIR/generator-markdown/`, having cleared that
   directory first and nothing else. Each run is echoed before it runs.
   - Why: the output root may also hold the other components' local runs, `collector-gh/` and `toolkit/`, and the
     example's `samples/`.
   - A run that fails stops the script with one line naming the document type, after the generator's log. An input of
     another contract stops it with the generator's own line; for a collector output, that line names the
     `living-doc-toolkit` command that writes the document type's input.
   - `main.py` gets a `GITHUB_OUTPUT` file under the venv, so its log does not report a missing one.
5. **Checks and reports** each document, with `tools/local_integration.py`:
   - It re-reads the input with `read_artifact`, then prints the input's contract and producer, the document's view
     and title, the run time, the document's and the run report's sizes, the run report's counts, the length of each
     render manifest list, and the input's warnings by code: each code's count and its first ten occurrences.
   - It fails on a missing or empty document or run report; on counts that differ from the input's
     `metadata.stats.cardinality`; on a view, the run report's or its manifest's, other than the input's
     `document.view`; and, for `technical-project` and `coverage-matrix`, on a manifest whose `entities` or
     `acceptance_criteria` are not as many as the counts.
   - The catalog is not held to the manifest check: its counts hold no entity or criterion, and count a scenario in
     each group that lists it, where its manifest lists the scenario once.
   - In the report, text from the files is printed with control characters spelled out (`\n`, `\x1b`), so an input
     cannot forge a report line. The generator's log lines above it are printed as the generator writes them.

- It exits non-zero when a check, the install, a run or a document's check fails.
- `tests/test_local_integration.py` holds its promises. The [CI](#ci) filter does not list the script, so a change to
  `local-integration.sh` alone runs no tests: run `make test`.
- For an issue or a report, keep the whole output: `set -o pipefail; ./local-integration.sh 2>&1 | tee local-integration.log`.

## Action venv

`action.yml` runs the generator in a venv of its own, built from the caller's Python.

- The action uses the Python on `PATH`; the caller prepares it, for example with `actions/setup-python`.
- Below 3.10 it fails before creating anything, with one line:
  `::error::living-doc-generator-markdown needs Python >= 3.10 on PATH. Add actions/setup-python before this step.`
- It installs `requirements.txt` into `$RUNNER_TEMP/living-doc-generator-markdown-venv`. It never changes the
  caller's interpreter, `PATH` or environment, and writes nothing to `$GITHUB_ENV` or `$GITHUB_PATH`.
- `PIP_TARGET`, `PIP_PREFIX`, `PIP_USER`, `PIP_ROOT`, `PIP_PYTHON` and `PYTHONPATH` are unset before the install.
  - Why: pip reads them as configuration, so a caller exporting one would empty or shadow the venv, or (`PIP_PYTHON`)
    install into the caller's own interpreter.
- The venv is reused only when the interpreter now on `PATH` built it, compared as `sys.base_prefix` plus version;
  otherwise it is rebuilt.
- After the install, one import of `living_doc_utilities` and `generator_markdown` through the venv's interpreter
  proves the packages landed there. Its failure is one line pointing at the runner's pip configuration.
- `main.py` runs with `-E`, so a caller's `PYTHONPATH` cannot shadow the venv. Every input reaches it through the
  run step's `env:`.
- Linux runners only: the venv's POSIX `bin/` layout is assumed.
- `tests/test_action_yml.py` runs the venv step against a fake interpreter. `integration_test.yml` shows the reuse,
  the rebuild on an interpreter change, and the rejection of Python 3.9 on real ones ([CI](#ci)).

## CI

`test.yml` runs the gates, `integration_test.yml` runs the action itself, and `link-check.yml` checks the Markdown
links.

- `QA Gate` is the job to mark as the one required check: it always runs, passes over a skipped job and fails on a
  failed or cancelled one.
  - Why: a required check must report on every pull request, also on one that changed no Python.
- The gates run when a Python-related file changed: `*.py`, `requirements.txt`, `requirements-dev.txt`,
  `pyproject.toml`, `Makefile`, `.pylintrc`, `action.yml`, `test.yml`, `templates/` or `tests/fixtures/`.
  - `templates/` and the golden snapshots under `tests/fixtures/` are in the list because a change to either changes
    the rendered output the tests compare.
  - `action.yml` is in the list because `tests/test_action_yml.py` reads it.
  - On a pull request a renamed file counts by its old path too, so moving a file out of that set still runs the
    tests.
- A manual run runs every gate, and `link-check.yml` checks every page.
  - Why: a manual run is a request to re-check the branch, whatever its last commit touched.
- `link-check.yml` skips the golden snapshots under `tests/fixtures/golden/`.
  - Why: they render the test samples, whose tracker and repository links are made up and do not resolve.
- `format-check`, `lint` and `types` run once, on Python 3.10.
  - Why: they give the same result on every interpreter, and on the floor a syntax newer than 3.10 fails.
- `make coverage` runs on Python 3.10 to 3.14.
  - Why: the action runs on whatever Python ≥ 3.10 the caller puts on `PATH`.
- `Contract Checks` runs `make no-vendored-schemas runtime-requirements` on every change.
  - Why: the checks read git's index and `requirements.txt`, not only Python.
  - With the static checks and the tests it covers every `make qa` target, so a local run and CI never drift.
- The isolation and rebuild jobs run the action through `uses: ./`, so a failed run fails the job, then assert on the
  venv, on the files written into `output-path` and on the `output-path` output. The 3.9 job runs it with
  `continue-on-error` and asserts the failure.
  - Why: a run that passed without writing its document and run report would be a broken action.
- The jobs need only `contents: read`: they run the repository's code and make no GitHub API call.
- Each job first writes the inputs it reads with `tools/write_sample_inputs.py` (`living-doc-utilities`'
  `full_sample()` and `write_artifact`), in a throwaway venv built from `requirements.txt`.
  - Why: no sample is committed, so the inputs always match the pinned contracts; the runner's interpreter is the
    one under test, and the isolation job breaks it on purpose.
- The isolation job installs `pydantic<2` into the runner's interpreter and compares its `python`, version and
  pydantic before and after. It runs on 3.12, a version pydantic 1.x publishes wheels for.
  - Why: `living-doc-utilities` cannot run on pydantic 1, so an action on that interpreter would fail its import
    check, and an action installing into it would replace that pydantic.
- It proves the reuse by `pyvenv.cfg`'s mtime, unchanged across its runs of the action.
  - Why: `python -m venv` without `--clear` keeps the files already in the directory, so a marker file survives a
    re-create; `pyvenv.cfg` is rewritten on every create.
- It renders all three document types, the third with a `document-title`. It then replays `main.py` on the action's
  venv, as the action runs it, on each input, and expects the input read, the run report and the `output-path` line.
  - Why: a failed install would stop on an import, and a wrong input on reading it.
- The rebuild job runs the action on 3.12, switches `setup-python` to 3.11, runs it again, and asks the venv's own
  interpreter for its version.
  - Why: the isolation job runs on one Python, so it cannot see the interpreter comparison; a reused venv would
    still report 3.12, so the version proves the rebuild, where an mtime would not.
- The 3.9 job writes its input on 3.12, switches to 3.9, and asserts that `PATH`'s Python is 3.9 before it
  checks the failure.
  - Why: otherwise it would also pass if `setup-python` resolved something newer and the action failed for another
    reason.
