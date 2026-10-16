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
The split between the two requirements files: `requirements.txt` is what the action installs into its venv
on every run, so it carries no test, lint or type tool; `requirements-dev.txt` adds those on top of it.
"""

from pathlib import Path

import pytest

from tools.check_runtime_requirements import RUNTIME_REQUIREMENTS, denied_requirements, main, requirement_name

REPO_ROOT = Path(__file__).resolve().parents[1]
DEV_REQUIREMENTS = REPO_ROOT / "requirements-dev.txt"


def _names(requirements_path: Path) -> list[str]:
    return [
        name
        for name in (requirement_name(line.split("#", 1)[0]) for line in requirements_path.read_text().splitlines())
        if name
    ]


def test_runtime_requirements_names_no_development_tool():
    # Assert: the check `make qa` runs, over the file it guards.
    assert denied_requirements(RUNTIME_REQUIREMENTS) == []
    assert main() == 0


def test_runtime_requirements_are_only_what_the_code_imports():
    # Assert: `utilities` 0.6.0 with no extra; pydantic and jsonschema arrive through it.
    assert _names(RUNTIME_REQUIREMENTS) == ["living-doc-utilities"]
    # The `utilities` version is this repository's own pin, so it is asserted exactly: a bump there is a
    # deliberate step, never a dependency update.
    assert "living-doc-utilities==0.6.0" in RUNTIME_REQUIREMENTS.read_text().splitlines()


def test_dev_requirements_include_the_runtime_set_and_the_gate_tools():
    # Arrange
    text = DEV_REQUIREMENTS.read_text()

    # Assert: the dev file builds on the runtime one, so `make install` installs both. Asserted by membership,
    # not by line number - a new header comment must not fail a file that is entirely correct.
    assert "-r requirements.txt" in text.splitlines()
    assert set(_names(DEV_REQUIREMENTS)) >= {"black", "mypy", "pylint", "pytest", "pytest-cov", "pyyaml", "ruff"}


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("pytest==9.1.1", "pytest"),
        ("PyYAML==6.0.3", "pyyaml"),
        ("typing_extensions==4.16.0", "typing-extensions"),
        ('tomli==2.4.1; python_version < "3.11"', "tomli"),
        ("living-doc-utilities[html]==0.6.0", "living-doc-utilities"),
        ("-r requirements.txt", ""),
        ("", ""),
        # PEP 503: a run of `-`, `_` or `.` is one `-`, so every spelling pip treats as one distribution
        # folds to one name - otherwise a dotted spelling walks past a deny list keyed on the hyphenated one.
        ("pytest.cov==7.1.0", "pytest-cov"),
        ("pytest..cov==7.1.0", "pytest-cov"),
        ("types.requests==2.33.0", "types-requests"),
        ("mypy.extensions==1.1.0", "mypy-extensions"),
    ],
)
def test_requirement_name_reads_the_distribution_a_line_names(line, expected):
    # Act & Assert
    assert requirement_name(line) == expected


@pytest.mark.parametrize(
    "line",
    [
        "pytest==9.1.1",
        "pytest-cov==7.1.0",
        "black==26.5.1",
        "mypy==2.3.1",
        "ruff==0.16.9",
        "types-requests==2.33.0",
        # The docstring promises "a test runner, linter, formatter or type checker", so a mainstream
        # alternative to the pinned ones must not slip past either.
        "pyright==1.1.0",
        "hypothesis==6.0.0",
        # A dotted spelling of a denied distribution: pip installs the same wheel, so the gate must too.
        "pytest.cov==7.1.0",
        "mypy.extensions==1.1.0",
    ],
)
def test_a_development_tool_in_the_runtime_file_is_reported(tmp_path, line):
    # Arrange
    planted = tmp_path / "requirements.txt"
    planted.write_text(f"living-doc-utilities==0.6.0\n{line}\n", encoding="utf-8")

    # Act & Assert: the offender is named, and the gate actually fails - not only the clean path is exercised.
    assert denied_requirements(planted) == [requirement_name(line)]
    assert main(planted) == 1


@pytest.mark.parametrize(
    "line",
    [
        # An include pulls in whatever the other file names. `requirements-dev.txt` includes this file, so
        # inverting the two would otherwise install the whole dev set into the action's venv, silently.
        "-r requirements-dev.txt",
        "--requirement requirements-dev.txt",
        # A VCS or URL reference hides the real distribution name from the deny list.
        "git+https://github.com/psf/black@main",
        "https://example.invalid/pytest-9.1.1-py3-none-any.whl",
        # A local path or wheel does the same.
        "./wheels/pytest-9.1.1-py3-none-any.whl",
    ],
)
def test_a_line_naming_no_plain_requirement_is_reported(tmp_path, line):
    # Arrange
    planted = tmp_path / "requirements.txt"
    planted.write_text(f"living-doc-utilities==0.6.0\n{line}\n", encoding="utf-8")

    # Act & Assert: the line itself is reported, since no distribution name can be read from it.
    assert denied_requirements(planted) == [line]
    assert main(planted) == 1


@pytest.mark.parametrize(
    "line",
    [
        "living-doc-utilities==0.6.0",
        'tomli==2.4.1; python_version < "3.11"',
        "living-doc-utilities[html]==0.6.0",
        "living-doc-utilities>=0.6.0,<0.7",
        "pydantic ~= 2.13",
    ],
)
def test_a_plain_runtime_pin_is_not_reported(tmp_path, line):
    # Arrange: every ordinary PEP 508 spelling a runtime file may use must pass cleanly.
    planted = tmp_path / "requirements.txt"
    planted.write_text(f"{line}\n", encoding="utf-8")

    # Act & Assert
    assert denied_requirements(planted) == []
    assert main(planted) == 0


def test_a_commented_out_development_tool_is_not_reported(tmp_path):
    # Arrange
    planted = tmp_path / "requirements.txt"
    planted.write_text("living-doc-utilities==0.6.0\n# pytest==9.1.1 lives in requirements-dev.txt\n", encoding="utf-8")

    # Act & Assert
    assert denied_requirements(planted) == []
