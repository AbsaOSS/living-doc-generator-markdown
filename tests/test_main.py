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
import logging
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
from living_doc_utilities.contracts import coverage_matrix, doc_source, generator_ready, ui_test_catalog
from living_doc_utilities.contracts.compat import installed_utilities_version

from main import RENDERING_NOT_IMPLEMENTED_MESSAGE, run

REPO_ROOT = Path(__file__).resolve().parents[1]
LOG_LINE = re.compile(r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d - [A-Z]+ - ")


def _errors(caplog) -> list[str]:
    assert all(record.exc_info is None for record in caplog.records)
    return [record.getMessage() for record in caplog.records if record.levelno >= logging.ERROR]


def _action_env(inputs: dict[str, str]) -> dict[str, str]:
    # Only the run step's inputs reach the entry point: no inherited `INPUT_*`, and no CI debug switch.
    env = {
        name: value for name, value in os.environ.items() if not name.startswith("INPUT_") and name != "RUNNER_DEBUG"
    }
    env.update(inputs)
    return env


def _run_entry_point(cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-E", os.fspath(REPO_ROOT / "main.py")],
        capture_output=True,
        check=False,
        cwd=cwd,
        env=env,
        text=True,
    )


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


@pytest.mark.parametrize(
    ("document_type", "contract_id"),
    [
        ("technical-project", generator_ready.CONTRACT_ID),
        ("ui-test-catalog", ui_test_catalog.CONTRACT_ID),
        ("coverage-matrix", coverage_matrix.CONTRACT_ID),
    ],
)
def test_a_run_with_a_valid_input_file_fails_because_rendering_is_not_implemented(
    valid_inputs, write_sample, monkeypatch, caplog, document_type, contract_id
):
    # Arrange
    write_sample(contract_id, "input.json")
    monkeypatch.setenv("INPUT_DOCUMENT_TYPE", document_type)
    monkeypatch.setenv("INPUT_SOURCE_PATH", "input.json")
    caplog.set_level(logging.INFO)

    # Act
    with pytest.raises(SystemExit) as exit_info:
        run()

    # Assert: the inputs were accepted and the file read, the run still fails, and nothing was written.
    assert exit_info.value.code == 1
    assert _errors(caplog) == [RENDERING_NOT_IMPLEMENTED_MESSAGE]
    assert f"Liv-Doc generator for Markdown - inputs valid: document type `{document_type}`" in caplog.text
    assert f"Liv-Doc generator for Markdown - input read: `{contract_id}`." in caplog.text
    assert not (valid_inputs / "output").exists()


def test_a_run_with_a_collector_output_fails_with_the_readers_one_line(valid_inputs, write_sample, monkeypatch, caplog):
    # Arrange
    write_sample(doc_source.CONTRACT_ID, "doc-source.json")
    monkeypatch.setenv("INPUT_SOURCE_PATH", "doc-source.json")
    caplog.set_level(logging.INFO)

    # Act
    with pytest.raises(SystemExit) as exit_info:
        run()

    # Assert: the run stops at the input file, before the not-implemented line.
    assert exit_info.value.code == 1
    assert _errors(caplog) == [
        "Input `source-path` is 'doc-source.json', a `doc-source` collector output; document type "
        "`technical-project` reads a `generator-ready` file, which the `living-doc-toolkit` command "
        "`normalize-docs` writes."
    ]
    assert "Liv-Doc generator for Markdown - input read:" not in caplog.text
    assert not (valid_inputs / "output").exists()


def test_the_not_implemented_message_is_one_line_naming_the_action():
    # Assert
    assert RENDERING_NOT_IMPLEMENTED_MESSAGE.startswith("Rendering is not implemented yet: ")
    assert "living-doc-generator-markdown" in RENDERING_NOT_IMPLEMENTED_MESSAGE
    assert "\n" not in RENDERING_NOT_IMPLEMENTED_MESSAGE


@pytest.mark.parametrize(
    ("inputs", "sample", "expected_error"),
    [
        ({}, None, "Input `document-type` is required"),
        ({"INPUT_DOCUMENT_TYPE": "technical-project"}, None, "Input `source-path` is required"),
        (
            {"INPUT_DOCUMENT_TYPE": "technical-project", "INPUT_SOURCE_PATH": "missing.json"},
            None,
            "Input `source-path` is 'missing.json', which does not exist.",
        ),
        ({"INPUT_DOCUMENT_TYPE": "technical-project"}, doc_source.CONTRACT_ID, "a `doc-source` collector output"),
        ({"INPUT_DOCUMENT_TYPE": "coverage-matrix"}, coverage_matrix.CONTRACT_ID, RENDERING_NOT_IMPLEMENTED_MESSAGE),
    ],
)
def test_the_entry_point_run_as_the_action_runs_it_prints_one_error_line(
    tmp_path, write_sample, inputs, sample, expected_error
):
    # Arrange: the input file lives outside the working directory, which must stay empty.
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    env = _action_env(inputs)
    if sample is not None:
        env["INPUT_SOURCE_PATH"] = os.fspath(write_sample(sample, tmp_path / "input" / f"{sample}.json"))

    # Act
    result = _run_entry_point(run_dir, env)

    # Assert
    assert result.returncode == 1
    assert all(LOG_LINE.match(line) for line in result.stdout.splitlines()), result.stdout
    assert "Traceback" not in result.stderr, result.stderr
    error_lines = [line for line in result.stdout.splitlines() if " - ERROR - " in line]
    assert len(error_lines) == 1, result.stdout
    assert expected_error in error_lines[0]
    assert list(run_dir.iterdir()) == []


def _valid_action_inputs(write_sample) -> dict[str, str]:
    write_sample(generator_ready.CONTRACT_ID, "input.json")
    return {"INPUT_DOCUMENT_TYPE": "technical-project", "INPUT_SOURCE_PATH": "input.json"}


@pytest.mark.parametrize("verbose_logging", ["true", "True"])
def test_verbose_logging_makes_the_entry_point_print_the_generators_debug_line(tmp_path, write_sample, verbose_logging):
    # Arrange
    inputs = {**_valid_action_inputs(write_sample), "INPUT_VERBOSE_LOGGING": verbose_logging}

    # Act
    result = _run_entry_point(tmp_path, _action_env(inputs))

    # Assert
    assert result.returncode == 1
    assert all(LOG_LINE.match(line) for line in result.stdout.splitlines()), result.stdout
    debug_lines = [line for line in result.stdout.splitlines() if " - DEBUG - " in line]
    assert any(
        "Liv-Doc generator for Markdown - input written by " in line
        and line.endswith(f" with living-doc-utilities {installed_utilities_version()!r}.")
        for line in debug_lines
    ), result.stdout


@pytest.mark.parametrize("verbose_logging", [None, "false"])
def test_without_verbose_logging_the_entry_point_prints_no_debug_line(tmp_path, write_sample, verbose_logging):
    # Arrange
    inputs = _valid_action_inputs(write_sample)
    if verbose_logging is not None:
        inputs["INPUT_VERBOSE_LOGGING"] = verbose_logging

    # Act
    result = _run_entry_point(tmp_path, _action_env(inputs))

    # Assert
    assert result.returncode == 1
    assert " - INFO - " in result.stdout
    assert " - DEBUG - " not in result.stdout
