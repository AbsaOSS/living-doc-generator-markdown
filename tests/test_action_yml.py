#
# Copyright 2026 ABSA Group Limited
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
"""
The `action.yml` promises a caller relies on: the action brings its own venv, writes nothing into the
caller's environment, rejects an unsupported Python with one actionable error, and takes exactly the inputs
`living-doc-generator-pdf` names, so the two generators stay interchangeable.

The integration workflow can prove the version check *fails*, but a composite action's step log is not
readable from a later workflow step, so the message itself is pinned here - otherwise a refactor to a bare
`exit 1` would regress the only guidance a caller gets, with every job still green.
"""

from pathlib import Path

import pytest
import yaml

from generator_markdown.action_inputs import DEFAULT_OUTPUT_PATH, DocumentType

REPO_ROOT = Path(__file__).resolve().parents[1]
ACTION_YML = REPO_ROOT / "action.yml"

PYTHON_FLOOR_ERROR = (
    "::error::living-doc-generator-markdown needs Python >= 3.10 on PATH. Add actions/setup-python before this step."
)
VENV_LINE = 'VENV="$RUNNER_TEMP/living-doc-generator-markdown-venv"'
INSTALL_LINE = '"$VENV/bin/pip" install -r "${{ github.action_path }}/requirements.txt"'
INPUTS = ["document-type", "source-path", "output-path", "document-title"]


def _action() -> dict:
    return yaml.safe_load(ACTION_YML.read_text(encoding="utf-8"))


def _code_lines() -> list[str]:
    return [line.split("#", 1)[0].strip() for line in ACTION_YML.read_text(encoding="utf-8").splitlines()]


def _step(step_id: str) -> dict:
    return next(step for step in _action()["runs"]["steps"] if step.get("id") == step_id)


def test_an_unsupported_python_fails_with_the_documented_one_line_error():
    # Assert: the exact string DEVELOPER.md's venv rule promises.
    assert PYTHON_FLOOR_ERROR in ACTION_YML.read_text(encoding="utf-8")


def test_the_version_floor_matches_the_one_the_project_requires():
    # Assert: the guard tests the same floor `pyproject.toml` declares, so the docs name one number.
    assert "sys.version_info >= (3, 10)" in ACTION_YML.read_text(encoding="utf-8")
    assert 'requires-python = ">=3.10"' in (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")


@pytest.mark.parametrize("leak", ["GITHUB_ENV", "GITHUB_PATH"])
def test_the_action_writes_nothing_into_the_callers_environment(leak):
    # Assert: every input is passed in the run step's own `env:`; nothing is exported to the job.
    code = [line.split("#", 1)[0] for line in ACTION_YML.read_text(encoding="utf-8").splitlines()]
    assert not [line for line in code if leak in line]


def test_the_action_installs_into_its_own_venv_and_never_the_runners_interpreter():
    # Assert: pip is always the venv's own, so no install reaches whatever interpreter the caller had.
    installs = [line for line in _code_lines() if "pip" in line and "install" in line]
    assert installs == [INSTALL_LINE]
    assert VENV_LINE in _code_lines()


def test_the_pip_environment_is_cleared_before_the_install():
    # Assert: unset, not set empty, and before pip runs - a caller's PIP_TARGET would otherwise empty the venv.
    lines = _code_lines()
    unset = "unset PIP_TARGET PIP_PREFIX PIP_USER PYTHONPATH"
    assert unset in lines
    assert lines.index(unset) < lines.index(INSTALL_LINE)


def test_the_venv_is_reused_only_when_the_interpreter_on_path_built_it():
    # Assert: the identity compared is the interpreter a venv was created from, plus its version; a mismatch
    # removes the venv before it is recreated.
    lines = _code_lines()
    assert "IDENTITY='import sys; print(sys.base_prefix, sys.version_info[:3])'" in lines
    assert lines.index('if [ "$HAVE" != "$WANT" ]; then') < lines.index('rm -rf "$VENV"')


def test_the_action_proves_the_requirements_and_its_package_import_in_the_venv():
    # Assert: the install is followed by an import through the venv's own interpreter, from the action's
    # directory. A runner `pip.conf` that redirects the packages (`target`/`prefix`, which no `unset` can
    # reach) leaves `pip install` green and the venv empty, so without this the first symptom is an import
    # error one step later.
    lines = _code_lines()
    checks = [
        line for line in lines if "\"$VENV/bin/python\" -c 'import living_doc_utilities, generator_markdown'" in line
    ]
    assert len(checks) == 1
    assert checks[0].startswith('(cd "${{ github.action_path }}" && ')
    assert lines.index(INSTALL_LINE) < lines.index(checks[0])


def test_the_entry_point_runs_through_the_venv_with_the_environment_ignored():
    # Assert: `-E`, so a caller's `PYTHONPATH` cannot shadow the venv's packages.
    assert _step("liv-doc-generator")["run"].strip().splitlines()[-1] == (
        '"${{ steps.venv.outputs.python }}" -E "${{ github.action_path }}/main.py"'
    )


def test_the_inputs_are_the_four_the_pdf_generator_names():
    # Assert: the same names as `living-doc-generator-pdf`, so a pipeline can switch generators.
    inputs = _action()["inputs"]
    assert list(inputs) == INPUTS
    assert inputs["document-type"]["required"] is True
    assert inputs["source-path"]["required"] is True
    assert inputs["output-path"]["required"] is False
    assert inputs["output-path"]["default"] == DEFAULT_OUTPUT_PATH
    assert inputs["document-title"]["required"] is False


def test_the_document_type_description_names_every_type_the_generator_accepts():
    # Assert: the description and `DocumentType` cannot drift apart.
    description = _action()["inputs"]["document-type"]["description"]
    assert [f"`{document_type.value}`" in description for document_type in DocumentType] == [True] * 3
    assert description.count("`") == 2 * len(DocumentType)


def test_every_input_reaches_the_entry_point_through_the_run_steps_env():
    # Assert: under `-E` the run step's `env:` is the only way in, so each input has its `INPUT_*` and nothing more.
    env = _step("liv-doc-generator")["env"]
    assert env == {f"INPUT_{name.replace('-', '_').upper()}": f"${{{{ inputs.{name} }}}}" for name in INPUTS}


def test_the_only_output_is_the_output_path_the_run_step_sets():
    # Assert
    outputs = _action()["outputs"]
    assert list(outputs) == ["output-path"]
    assert outputs["output-path"]["value"] == "${{ steps.liv-doc-generator.outputs.output-path }}"
