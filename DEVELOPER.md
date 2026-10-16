# Living Documentation Generator for Markdown: developer guide

## Purpose

Anyone who changes this repository reads this page. It covers setup, the quality gates, a debug run, and the rules
the action's venv follows.

Read before: [README](README.md)

## Contents

- [Setup](#setup)
- [Gates](#gates)
- [Debug run](#debug-run)
- [Action venv](#action-venv)

## Setup

1. Use Python 3.10 or later: `python3 --version`.
2. Create and activate a virtual environment: `python3 -m venv .venv`, then `source .venv/bin/activate`.
3. Run `make install`: `pip install -r requirements-dev.txt`, which pulls in `requirements.txt`.

| File | What it holds | Who installs it |
|---|---|---|
| `requirements.txt` | Runtime only: `living-doc-utilities`, the one package `main.py` and `generator_markdown/` import | `action.yml`, into its venv, on every run |
| `requirements-dev.txt` | `-r requirements.txt`, the gate and test tools, and `PyYAML` for `tests/test_action_yml.py` | `make install` and `test.yml` |

- The supported floor is 3.10, as `pyproject.toml` `requires-python` states; CI tests 3.10 through 3.14.
- A test, lint or type tool in `requirements.txt` would download on every run of every caller; `make qa` fails on one.
- Dependabot covers both files from its single `pip` entry in `.github/dependabot.yml`.

## Gates

`make qa` runs `format-check`, `lint`, `types`, `runtime-requirements` and `coverage`, and stops at the first
failure. Run it before opening a pull request.

| Target | Runs | Gate |
|---|---|---|
| `make format` | ruff autofix, then Black, rewriting files | line length 120 |
| `make format-check` | Black in check mode | clean |
| `make lint` | ruff, then Pylint; Pylint skips `tests/` | Pylint ≥ 9.5 / 10 (`PYLINT_MIN`) |
| `make types` | mypy over the project; `tests/` is excluded | clean |
| `make runtime-requirements` | `tools/check_runtime_requirements.py` | no test, lint or type tool in `requirements.txt` |
| `make test` | pytest over `tests/` | pass |
| `make coverage` | pytest with coverage; `tests/` is not measured | ≥ 80 % (`COV_MIN`) |

- `test.yml` calls the same targets: the static checks once on Python 3.10, `runtime-requirements` on every
  change, `make coverage` on 3.10 to 3.14, all behind one `QA Gate` job.
- Black, ruff and Pylint take their files from `git ls-files`, so a new file is checked once it is tracked.
- Black, ruff and mypy read their settings from `pyproject.toml`; Pylint reads `.pylintrc`. `make help` lists
  every target.

## Debug run

```shell
export INPUT_DOCUMENT_TYPE=technical-project            # required: technical-project, ui-test-catalog or coverage-matrix
export INPUT_SOURCE_PATH=generator-ready.json           # required
export INPUT_OUTPUT_PATH=./output/generator-markdown    # the default
python3 main.py
```

- Each input is an `INPUT_<NAME>` variable, upper case with `_` for `-`, as `action.yml` passes it.
- Rendering is not implemented yet: a run with valid inputs ends with `Rendering is not implemented yet: …` and
  exit code 1, and writes nothing.

## Action venv

`action.yml` runs the generator in a venv of its own, built from the caller's Python.

- The action uses the Python on `PATH`; the caller prepares it, for example with `actions/setup-python`.
- Below 3.10 it fails before creating anything, with one line:
  `::error::living-doc-generator-markdown needs Python >= 3.10 on PATH. Add actions/setup-python before this step.`
- It installs `requirements.txt` into `$RUNNER_TEMP/living-doc-generator-markdown-venv`. It never changes the
  caller's interpreter, `PATH` or environment, and writes nothing to `$GITHUB_ENV` or `$GITHUB_PATH`.
- `PIP_TARGET`, `PIP_PREFIX`, `PIP_USER` and `PYTHONPATH` are unset before the install.
  - Why: pip reads them as configuration, so a caller exporting one would empty or shadow the venv.
- The venv is reused only when the interpreter now on `PATH` built it, compared as `sys.base_prefix` plus version;
  otherwise it is rebuilt.
- After the install, one import of `living_doc_utilities` and `generator_markdown` through the venv's interpreter
  proves the packages landed there. Its failure is one line pointing at the runner's pip configuration.
- `main.py` runs with `-E`, so a caller's `PYTHONPATH` cannot shadow the venv. Every input reaches it through the
  run step's `env:`.
- Linux runners only: the venv's POSIX `bin/` layout is assumed.
- `tests/test_action_yml.py` pins each rule in `action.yml`. `integration_test.yml` shows the reuse, the rebuild on
  an interpreter change, and the rejection of Python 3.9.
