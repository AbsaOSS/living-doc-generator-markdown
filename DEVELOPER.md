# Living Documentation Generator for Markdown: developer guide

## Purpose

Anyone who changes this repository reads this page. It covers setup, the quality gates, the design rules the
rendering keeps, a debug run, the rules the action's venv follows, and what CI runs.

Read before: [README](README.md)

## Contents

- [Setup](#setup)
- [Gates](#gates)
- [Design rules](#design-rules)
- [Debug run](#debug-run)
- [Action venv](#action-venv)
- [CI](#ci)

## Setup

1. Use Python 3.10 or later: `python3 --version`.
2. Create and activate a virtual environment: `python3 -m venv .venv`, then `source .venv/bin/activate`.
3. Run `make install`: `pip install -r requirements-dev.txt`, which pulls in `requirements.txt`.

| File | What it holds | Who installs it |
|---|---|---|
| `requirements.txt` | Runtime only: `living-doc-utilities` and `Jinja2`, the packages `main.py` and `generator_markdown/` import | `action.yml`, into its venv, on every run |
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
