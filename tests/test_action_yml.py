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
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from generator_markdown.action_inputs import DEFAULT_OUTPUT_PATH

REPO_ROOT = Path(__file__).resolve().parents[1]
ACTION = yaml.safe_load((REPO_ROOT / "action.yml").read_text(encoding="utf-8"))
STEPS = {step["id"]: step for step in ACTION["runs"]["steps"]}
INPUTS = ["document-type", "source-path", "output-path", "document-title"]
PIP_ENVIRONMENT = ["PIP_TARGET", "PIP_PREFIX", "PIP_USER", "PIP_ROOT", "PIP_PYTHON", "PYTHONPATH"]

# Stands in for every interpreter the venv step calls: `-c` code runs on this test's interpreter, with the fake's
# version and prefix when given; `-m venv DIR` fills DIR with a copy of the fake and a pip that only logs its call.
FAKE_PYTHON = """#!{executable}
import os, shutil, sys
with open({calls!r}, "a", encoding="utf-8") as calls:
    calls.write(" ".join(sys.argv) + "\\n")
args = [arg for arg in sys.argv[1:] if arg != "-E"]
if args[:2] == ["-m", "venv"]:
    if not {venv_ok!r}:
        sys.exit(1)
    os.makedirs(os.path.join(args[2], "bin"))
    shutil.copy(__file__, os.path.join(args[2], "bin", "python"))
    shutil.copy({pip!r}, os.path.join(args[2], "bin", "pip"))
    sys.exit(0)
if {version!r}:
    sys.version_info = {version!r}
if {prefix!r}:
    sys.base_prefix = {prefix!r}
if not {importable!r}:
    sys.modules["living_doc_utilities"] = None
sys.path[0] = ""
exec(args[1])
"""
FAKE_PIP = """#!/bin/sh
echo "$0 $*" >> "{calls}"
env > "{calls}.env"
"""


def _venv(tmp_path: Path) -> Path:
    return tmp_path / "runner" / "living-doc-generator-markdown-venv"


def _write_fake_python(path: Path, tmp_path: Path, version=None, prefix=None, venv_ok=True, importable=True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        FAKE_PYTHON.format(
            executable=sys.executable,
            calls=os.fspath(tmp_path / "python.calls"),
            pip=os.fspath(tmp_path / "pip"),
            version=version,
            prefix=prefix,
            venv_ok=venv_ok,
            importable=importable,
        ),
        encoding="utf-8",
    )
    path.chmod(0o755)


def _run_venv_step(tmp_path: Path, env: dict[str, str] | None = None, **fake) -> subprocess.CompletedProcess:
    _write_fake_python(tmp_path / "bin" / "python3", tmp_path, **fake)
    pip = tmp_path / "pip"
    pip.write_text(FAKE_PIP.format(calls=tmp_path / "pip.calls"), encoding="utf-8")
    pip.chmod(0o755)
    (tmp_path / "runner").mkdir(exist_ok=True)
    script = STEPS["venv"]["run"].replace("${{ github.action_path }}", os.fspath(REPO_ROOT))
    return subprocess.run(
        ["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", script],
        capture_output=True,
        check=False,
        cwd=tmp_path,
        env={
            "PATH": f"{tmp_path / 'bin'}{os.pathsep}{os.environ['PATH']}",
            "RUNNER_TEMP": os.fspath(tmp_path / "runner"),
            "GITHUB_OUTPUT": os.fspath(tmp_path / "github-output"),
            "GITHUB_ENV": os.fspath(tmp_path / "github-env"),
            "GITHUB_PATH": os.fspath(tmp_path / "github-path"),
            **(env or {}),
        },
        text=True,
    )


def _errors(result: subprocess.CompletedProcess) -> list[str]:
    return [line for line in result.stdout.splitlines() if line.startswith("::error::")]


def _venv_creations(tmp_path: Path) -> int:
    return sum(" -m venv " in line for line in (tmp_path / "python.calls").read_text(encoding="utf-8").splitlines())


def test_the_inputs_are_the_four_the_pdf_generator_names():
    # Assert
    inputs = ACTION["inputs"]
    assert list(inputs) == INPUTS
    assert [inputs[name]["required"] for name in INPUTS] == [True, True, False, False]
    assert inputs["output-path"]["default"] == DEFAULT_OUTPUT_PATH


def test_every_input_reaches_the_entry_point_through_the_run_steps_env():
    # Assert
    assert STEPS["liv-doc-generator"]["env"] == {
        f"INPUT_{name.replace('-', '_').upper()}": f"${{{{ inputs.{name} }}}}" for name in INPUTS
    }


def test_the_run_step_runs_the_entry_point_on_the_venv_interpreter_ignoring_the_environment():
    # Assert
    assert STEPS["liv-doc-generator"]["run"].strip() == (
        '"${{ steps.venv.outputs.python }}" -E "${{ github.action_path }}/main.py"'
    )


def test_the_only_output_is_the_run_steps_output_path():
    # Assert
    assert ACTION["outputs"]["output-path"]["value"] == "${{ steps.liv-doc-generator.outputs.output-path }}"
    assert list(ACTION["outputs"]) == ["output-path"]


def test_a_python_below_3_10_fails_with_one_error_line_before_creating_a_venv(tmp_path):
    # Act
    result = _run_venv_step(tmp_path, version=(3, 9, 18))

    # Assert
    assert result.returncode == 1
    assert len(_errors(result)) == 1
    assert not _venv(tmp_path).exists()


def test_a_failed_venv_create_fails_with_one_error_line(tmp_path):
    # Act
    result = _run_venv_step(tmp_path, venv_ok=False)

    # Assert
    assert result.returncode == 1
    assert len(_errors(result)) == 1


def test_only_the_runtime_requirements_install_through_the_venvs_pip_with_the_pip_environment_cleared(tmp_path):
    # Arrange
    leaked = {name: os.fspath(tmp_path / "elsewhere") for name in PIP_ENVIRONMENT}

    # Act
    result = _run_venv_step(tmp_path, env=leaked)

    # Assert
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "pip.calls").read_text(encoding="utf-8").splitlines() == [
        f"{_venv(tmp_path)}/bin/pip install -r {REPO_ROOT}/requirements.txt"
    ]
    pip_env = (tmp_path / "pip.calls.env").read_text(encoding="utf-8").splitlines()
    assert [line for line in pip_env if line.split("=", 1)[0] in PIP_ENVIRONMENT] == []


def test_a_good_install_hands_the_venv_interpreter_to_the_run_step_and_nothing_to_the_job(tmp_path):
    # Act
    result = _run_venv_step(tmp_path)

    # Assert
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "github-output").read_text(encoding="utf-8") == f"python={_venv(tmp_path)}/bin/python\n"
    assert not (tmp_path / "github-env").exists()
    assert not (tmp_path / "github-path").exists()


def test_requirements_missing_from_the_venv_fail_the_import_check_with_one_error_line(tmp_path):
    # Act
    result = _run_venv_step(tmp_path, importable=False)

    # Assert
    assert result.returncode == 1
    assert len(_errors(result)) == 1
    assert not (tmp_path / "github-output").exists()


def test_the_venv_is_reused_when_the_interpreter_on_path_built_it(tmp_path):
    # Arrange
    _run_venv_step(tmp_path)

    # Act
    result = _run_venv_step(tmp_path)

    # Assert
    assert result.returncode == 0, result.stderr
    assert _venv_creations(tmp_path) == 1


@pytest.mark.parametrize("built_by", [{"prefix": "/opt/another-python"}, {"version": (3, 99, 0)}])
def test_the_venv_is_rebuilt_when_another_interpreter_built_it(tmp_path, built_by):
    # Arrange
    _write_fake_python(_venv(tmp_path) / "bin" / "python", tmp_path, **built_by)

    # Act
    result = _run_venv_step(tmp_path)

    # Assert
    assert result.returncode == 0, result.stderr
    assert _venv_creations(tmp_path) == 1
