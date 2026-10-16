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
The run as a caller sees it: every run fails with exit code 1 and exactly one error line - the invalid input it
names, or, for valid inputs, the message that rendering is not implemented yet.
"""

import logging
import os
import subprocess
import sys
from pathlib import Path

import pytest

from main import RENDERING_NOT_IMPLEMENTED_MESSAGE, run

REPO_ROOT = Path(__file__).resolve().parents[1]


def _errors(caplog) -> list[str]:
    return [record.getMessage() for record in caplog.records if record.levelno >= logging.ERROR]


def test_a_run_with_no_input_fails_with_one_line_naming_the_input(caplog):
    # Act
    with pytest.raises(SystemExit) as exit_info:
        run()

    # Assert
    assert exit_info.value.code == 1
    assert _errors(caplog) == [
        "Input `document-type` is required; valid types: technical-project, ui-test-catalog, coverage-matrix."
    ]


def test_a_run_with_an_unknown_document_type_fails_listing_the_valid_types(valid_inputs, monkeypatch, caplog):
    # Arrange
    monkeypatch.setenv("INPUT_DOCUMENT_TYPE", "pdf")

    # Act
    with pytest.raises(SystemExit) as exit_info:
        run()

    # Assert
    assert exit_info.value.code == 1
    assert _errors(caplog) == [
        "Input `document-type` is 'pdf', not a valid type; "
        "valid types: technical-project, ui-test-catalog, coverage-matrix."
    ]


def test_a_run_with_valid_inputs_fails_because_rendering_is_not_implemented(valid_inputs, caplog):
    # Arrange
    caplog.set_level(logging.INFO)

    # Act
    with pytest.raises(SystemExit) as exit_info:
        run()

    # Assert: the inputs were accepted, the run still fails, and nothing was written.
    assert exit_info.value.code == 1
    assert _errors(caplog) == [RENDERING_NOT_IMPLEMENTED_MESSAGE]
    assert "Liv-Doc generator for Markdown - inputs valid: document type `technical-project`" in caplog.text
    assert not (valid_inputs / "output").exists()


def test_the_not_implemented_message_is_one_line_naming_the_action():
    # Assert
    assert RENDERING_NOT_IMPLEMENTED_MESSAGE.startswith("Rendering is not implemented yet: ")
    assert "living-doc-generator-markdown" in RENDERING_NOT_IMPLEMENTED_MESSAGE
    assert "\n" not in RENDERING_NOT_IMPLEMENTED_MESSAGE


@pytest.mark.parametrize(
    ("inputs", "expected_error"),
    [
        ({}, "Input `document-type` is required"),
        ({"INPUT_DOCUMENT_TYPE": "technical-project"}, "Input `source-path` is required"),
        (
            {"INPUT_DOCUMENT_TYPE": "coverage-matrix", "INPUT_SOURCE_PATH": "coverage-matrix.json"},
            "Rendering is not implemented yet",
        ),
    ],
)
def test_the_entry_point_run_as_the_action_runs_it_prints_one_error_line(tmp_path, inputs, expected_error):
    # Arrange: `-E` and the inputs as the run step's `env:` passes them, nothing else of the caller's `INPUT_*`.
    env = {name: value for name, value in os.environ.items() if not name.startswith("INPUT_")}
    env.update(inputs)

    # Act
    result = subprocess.run(
        [sys.executable, "-E", os.fspath(REPO_ROOT / "main.py")],
        capture_output=True,
        check=False,
        cwd=tmp_path,
        env=env,
        text=True,
    )

    # Assert
    assert result.returncode == 1
    error_lines = [line for line in result.stdout.splitlines() if " - ERROR - " in line]
    assert len(error_lines) == 1, result.stdout
    assert expected_error in error_lines[0]
    assert list(tmp_path.iterdir()) == []
