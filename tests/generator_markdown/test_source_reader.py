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
import json
import os
import sys
from pathlib import Path

import pytest
from living_doc_utilities.contracts import (
    coverage_matrix,
    doc_entities,
    doc_source,
    generator_ready,
    registry,
    ui_test_catalog,
    ui_tests,
)
from living_doc_utilities.contracts.compat import installed_utilities_version

from generator_markdown.action_inputs import DocumentType
from generator_markdown.source_reader import (
    COLLECTOR_CONTRACT_NAMES,
    CONTRACT_NAMES,
    TOOLKIT_COMMANDS,
    SourceInputError,
    read_source,
)

SOURCE = "input.json"
COLLECTOR_OUTPUTS = [
    (doc_source.CONTRACT_ID, "doc-source"),
    (doc_entities.CONTRACT_ID, "doc-entities"),
    (ui_tests.CONTRACT_ID, "ui-tests"),
]


@pytest.fixture(autouse=True)
def _run_in_tmp_path(monkeypatch, tmp_path):
    # Relative names keep the path every message quotes short and deterministic.
    monkeypatch.chdir(tmp_path)


@pytest.fixture(name="unreadable_source")
def _unreadable_source(write_sample):
    source = write_sample(generator_ready.CONTRACT_ID, SOURCE)
    source.chmod(0o000)
    if os.access(source, os.R_OK):
        source.chmod(0o600)
        pytest.skip("this user or file system reads a file whatever its mode")
    yield source
    # Readable again, so the `tmp_path` cleanup can remove it.
    source.chmod(0o600)


@pytest.fixture(name="int_digit_limit")
def _int_digit_limit():
    if not hasattr(sys, "set_int_max_str_digits"):
        pytest.skip("this Python has no integer digit limit")
    previous = sys.get_int_max_str_digits()
    sys.set_int_max_str_digits(4300)
    yield 4300
    sys.set_int_max_str_digits(previous)


def _rejected(document_type: DocumentType, source_path: str = SOURCE) -> SourceInputError:
    with pytest.raises(SourceInputError) as error:
        read_source(document_type, source_path)
    message = str(error.value)
    # Every rejection is the one line the run fails with, naming the input.
    assert message.startswith("Input `source-path` is ")
    assert "\n" not in message
    return error.value


def _rejection(document_type: DocumentType, source_path: str = SOURCE) -> str:
    return str(_rejected(document_type, source_path))


def _utilities_message(error: SourceInputError) -> str:
    # The `utilities` wording is its own; the generator only keeps it, on one line.
    return " ".join(str(error.__cause__).split())


def test_every_document_type_reads_one_toolkit_contract_written_by_one_toolkit_command():
    # Assert
    assert set(CONTRACT_NAMES) == set(DocumentType)
    assert set(TOOLKIT_COMMANDS) == set(DocumentType)


def test_every_contract_the_installed_utilities_knows_is_a_collector_output_or_a_document_types_input():
    # Arrange
    names = {contract_id.rsplit("-v", 1)[0] for contract_id in registry.CONTRACTS}

    # Assert: a new contract would fall to the generic line, without a hint.
    assert names == COLLECTOR_CONTRACT_NAMES | set(CONTRACT_NAMES.values())


@pytest.mark.parametrize(
    ("document_type", "contract_id", "model"),
    [
        (DocumentType.TECHNICAL_PROJECT, generator_ready.CONTRACT_ID, generator_ready.GeneratorReadyResult),
        (DocumentType.UI_TEST_CATALOG, ui_test_catalog.CONTRACT_ID, ui_test_catalog.UiTestCatalogResult),
        (DocumentType.COVERAGE_MATRIX, coverage_matrix.CONTRACT_ID, coverage_matrix.CoverageMatrixResult),
    ],
)
def test_a_valid_file_is_read_as_the_typed_model_of_the_contract_its_document_type_renders(
    write_sample, document_type, contract_id, model
):
    # Arrange
    write_sample(contract_id, SOURCE)

    # Act
    document = read_source(document_type, SOURCE)

    # Assert
    assert isinstance(document, model)
    assert document.schema_version == contract_id


@pytest.mark.parametrize(("contract_id", "contract_name"), COLLECTOR_OUTPUTS)
@pytest.mark.parametrize(
    ("document_type", "expected", "command"),
    [
        ("technical-project", "generator-ready", "normalize-docs"),
        ("ui-test-catalog", "ui-test-catalog", "normalize-tests"),
        ("coverage-matrix", "coverage-matrix", "coverage-matrix"),
    ],
)
def test_a_collector_output_is_rejected_naming_the_toolkit_command_that_writes_the_input(
    write_sample, document_type, expected, command, contract_id, contract_name
):
    # Arrange
    write_sample(contract_id, SOURCE)

    # Act
    message = _rejection(DocumentType(document_type))

    # Assert
    assert message == (
        f"Input `source-path` is 'input.json', a `{contract_name}` collector output; document type "
        f"`{document_type}` reads a `{expected}` file, which the `living-doc-toolkit` command `{command}` writes."
    )


@pytest.mark.parametrize(
    ("document_type", "expected", "contract_id", "contract_name", "rendered_by"),
    [
        ("technical-project", "generator-ready", ui_test_catalog.CONTRACT_ID, "ui-test-catalog", "ui-test-catalog"),
        ("technical-project", "generator-ready", coverage_matrix.CONTRACT_ID, "coverage-matrix", "coverage-matrix"),
        ("ui-test-catalog", "ui-test-catalog", generator_ready.CONTRACT_ID, "generator-ready", "technical-project"),
        ("ui-test-catalog", "ui-test-catalog", coverage_matrix.CONTRACT_ID, "coverage-matrix", "coverage-matrix"),
        ("coverage-matrix", "coverage-matrix", generator_ready.CONTRACT_ID, "generator-ready", "technical-project"),
        ("coverage-matrix", "coverage-matrix", ui_test_catalog.CONTRACT_ID, "ui-test-catalog", "ui-test-catalog"),
    ],
)
def test_another_document_types_input_is_rejected_naming_the_document_type_that_renders_it(
    write_sample, document_type, expected, contract_id, contract_name, rendered_by
):
    # Arrange
    write_sample(contract_id, SOURCE)

    # Act
    message = _rejection(DocumentType(document_type))

    # Assert
    assert message == (
        f"Input `source-path` is 'input.json', a `{contract_name}` file, which document type `{rendered_by}` "
        f"renders; document type `{document_type}` reads a `{expected}` file."
    )


@pytest.mark.parametrize("source_path", ["missing.json", "./missing.json", "absent/directory/input.json"])
def test_a_missing_file_is_rejected_quoting_the_path_as_given(source_path):
    # Act
    message = _rejection(DocumentType.TECHNICAL_PROJECT, source_path)

    # Assert
    assert message == f"Input `source-path` is {source_path!r}, which does not exist."


def test_a_directory_is_rejected_as_not_a_json_file(tmp_path):
    # Arrange
    (tmp_path / "docs").mkdir()

    # Act
    message = _rejection(DocumentType.TECHNICAL_PROJECT, "docs")

    # Assert
    assert message == "Input `source-path` is 'docs', a directory, not a JSON file."


def test_an_unreadable_file_is_rejected_with_the_reason(unreadable_source):
    # Act
    message = _rejection(DocumentType.TECHNICAL_PROJECT)

    # Assert
    assert message == "Input `source-path` is 'input.json', which cannot be read: Permission denied."


def test_a_file_that_is_not_utf_8_is_rejected_naming_the_byte(tmp_path):
    # Arrange
    (tmp_path / SOURCE).write_bytes(b"\xff")

    # Act
    message = _rejection(DocumentType.TECHNICAL_PROJECT)

    # Assert
    assert message == "Input `source-path` is 'input.json', which is not UTF-8 text: invalid start byte at byte 0."


def test_a_file_that_is_not_json_is_rejected_naming_the_line_and_column(tmp_path):
    # Arrange
    (tmp_path / SOURCE).write_text("{", encoding="utf-8")

    # Act
    message = _rejection(DocumentType.TECHNICAL_PROJECT)

    # Assert
    assert message == (
        "Input `source-path` is 'input.json', which is not JSON: "
        "Expecting property name enclosed in double quotes at line 1, column 2."
    )


def test_an_empty_file_is_rejected_as_not_json(tmp_path):
    # Arrange
    (tmp_path / SOURCE).write_text("", encoding="utf-8")

    # Act
    message = _rejection(DocumentType.TECHNICAL_PROJECT)

    # Assert
    assert message == "Input `source-path` is 'input.json', which is not JSON: Expecting value at line 1, column 1."


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="no FIFO on this platform")
def test_a_fifo_is_rejected_as_not_a_regular_file_without_reading_it(tmp_path):
    # Arrange: reading a FIFO with no writer would block the run.
    os.mkfifo(tmp_path / "pipe")

    # Act
    message = _rejection(DocumentType.TECHNICAL_PROJECT, "pipe")

    # Assert
    assert message == "Input `source-path` is 'pipe', not a regular file."


def test_json_nested_past_the_recursion_limit_is_rejected_on_one_line(tmp_path):
    # Arrange: deep enough for every supported Python's decoder.
    depth = 1_000_000
    (tmp_path / SOURCE).write_text("[" * depth + "]" * depth, encoding="utf-8")

    # Act
    message = _rejection(DocumentType.TECHNICAL_PROJECT)

    # Assert
    assert message == "Input `source-path` is 'input.json', which is nested too deeply to read."


def test_an_integer_past_pythons_digit_limit_is_rejected_without_pythons_advice(tmp_path, int_digit_limit):
    # Arrange
    (tmp_path / SOURCE).write_text(
        '{"schema_version": "generator-ready-v1.0.0", "n": ' + "1" * (int_digit_limit + 1) + "}", encoding="utf-8"
    )

    # Act
    message = _rejection(DocumentType.TECHNICAL_PROJECT)

    # Assert: the action user cannot raise the limit, so the message does not tell them to.
    assert message.startswith("Input `source-path` is 'input.json', which cannot be loaded: ")
    assert "set_int_max_str_digits" not in message
    assert message.endswith(".")


def test_a_value_a_contract_model_cannot_report_is_rejected_on_one_printable_line(write_sample):
    # Arrange: a lone surrogate in a repository the model rejects; pydantic cannot encode the model's own message.
    source = write_sample(generator_ready.CONTRACT_ID, SOURCE)
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["metadata"]["source"]["repositories"] = ["\ud800/repository"]
    source.write_text(json.dumps(payload), encoding="utf-8")

    # Act
    message = _rejection(DocumentType.TECHNICAL_PROJECT)

    # Assert: whichever line names the cause, it can be printed.
    assert message.startswith("Input `source-path` is 'input.json', ")
    assert message.isprintable()


@pytest.mark.parametrize("content", ["{}", "[]", '{"schema_version": 1}', '{"schema_version": "generator-ready"}'])
def test_a_file_without_a_valid_schema_version_is_rejected_as_an_invalid_contract_id(tmp_path, content):
    # Arrange
    (tmp_path / SOURCE).write_text(content, encoding="utf-8")

    # Act
    error = _rejected(DocumentType.TECHNICAL_PROJECT)

    # Assert
    assert (
        str(error)
        == f"Input `source-path` is 'input.json', not a valid `generator-ready` file: {_utilities_message(error)}"
    )
    assert _utilities_message(error).startswith("[INVALID_CONTRACT_ID] ")


def test_a_schema_invalid_file_is_rejected_keeping_the_utilities_pin_hint(write_sample):
    # Arrange: a `generator-ready` file with no `document`, written by another utilities version.
    source = write_sample(generator_ready.CONTRACT_ID, SOURCE)
    payload = json.loads(source.read_text(encoding="utf-8"))
    del payload["document"]
    payload["metadata"]["producer"]["utilities_version"] = "0.0.1"
    source.write_text(json.dumps(payload), encoding="utf-8")

    # Act
    error = _rejected(DocumentType.TECHNICAL_PROJECT)

    # Assert
    assert (
        str(error)
        == f"Input `source-path` is 'input.json', not a valid `generator-ready` file: {_utilities_message(error)}"
    )
    assert _utilities_message(error).startswith("[SCHEMA_VALIDATION_FAILED] ")
    assert str(error).endswith("align the pins")


def test_a_long_rejection_is_cut_in_the_middle_keeping_the_utilities_pin_hint(write_sample):
    # Arrange: the schema error quotes the 100 000-character value it rejects.
    source = write_sample(generator_ready.CONTRACT_ID, SOURCE)
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["document"] = "x" * 100_000
    payload["metadata"]["producer"]["utilities_version"] = "0.0.1"
    source.write_text(json.dumps(payload), encoding="utf-8")

    # Act
    message = _rejection(DocumentType.TECHNICAL_PROJECT)

    # Assert
    assert message.startswith(
        "Input `source-path` is 'input.json', not a valid `generator-ready` file: [SCHEMA_VALIDATION_FAILED] "
    )
    assert len(message) < 1200
    assert " … " in message
    assert message.endswith("align the pins")


def test_a_file_failing_model_validation_is_rejected_on_one_line(write_sample):
    # Arrange: a coverage matrix whose summary no longer matches its rows passes the schema, not the model.
    source = write_sample(coverage_matrix.CONTRACT_ID, SOURCE)
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["summary"]["covered_acs"] += 1
    source.write_text(json.dumps(payload), encoding="utf-8")

    # Act
    error = _rejected(DocumentType.COVERAGE_MATRIX)

    # Assert: pydantic's report spans lines; the message the run fails with does not.
    assert "\n" in str(error.__cause__)
    assert (
        str(error)
        == f"Input `source-path` is 'input.json', not a valid `coverage-matrix` file: {_utilities_message(error)}"
    )
    assert _utilities_message(error).startswith("[SCHEMA_VALIDATION_FAILED] ")


@pytest.mark.parametrize(
    "schema_version",
    [
        "generator-ready-v9.9.9",
        # `utilities` accepts a trailing line break in `schema_version`; the quoted name keeps the message one line.
        "generator-ready-v1.0.0\n",
        # A digit that is not ASCII matches `utilities`' pattern and names no schema file.
        "generator-ready-v١.0.0",
        # A schema file name past the file system's limit cannot be opened at all.
        "generator-ready-v" + "1" * 300 + ".0.0",
    ],
)
def test_a_version_of_the_expected_contract_the_installed_utilities_lacks_is_rejected_with_the_pin_hint(
    tmp_path, schema_version
):
    # Arrange
    (tmp_path / SOURCE).write_text(json.dumps({"schema_version": schema_version}), encoding="utf-8")

    # Act
    error = _rejected(DocumentType.TECHNICAL_PROJECT)

    # Assert
    assert isinstance(error.__cause__, OSError)
    schema_file = Path(os.fspath(error.__cause__.filename)).name
    assert str(error) == (
        f"Input `source-path` is 'input.json', a `generator-ready` version living-doc-utilities "
        f"{installed_utilities_version()} ships no schema for ({schema_file!r}); check its `schema_version`, "
        "or align the pins if the components run different utilities versions."
    )


def test_a_long_unshipped_version_is_cut_in_the_middle_keeping_the_pin_hint(tmp_path):
    # Arrange
    (tmp_path / SOURCE).write_text(
        json.dumps({"schema_version": "generator-ready-v" + "1" * 100_000 + ".0.0"}), encoding="utf-8"
    )

    # Act
    message = _rejection(DocumentType.TECHNICAL_PROJECT)

    # Assert
    assert message.startswith("Input `source-path` is 'input.json', a `generator-ready` version living-doc-utilities ")
    assert len(message) < 1300
    assert " … " in message
    assert message.endswith("or align the pins if the components run different utilities versions.")


def test_an_unknown_contract_is_rejected_as_a_contract_mismatch(tmp_path):
    # Arrange
    (tmp_path / SOURCE).write_text('{"schema_version": "foo-v1.0.0"}', encoding="utf-8")

    # Act
    error = _rejected(DocumentType.TECHNICAL_PROJECT)

    # Assert
    assert (
        str(error)
        == f"Input `source-path` is 'input.json', not a valid `generator-ready` file: {_utilities_message(error)}"
    )
    assert _utilities_message(error).startswith("[CONTRACT_MISMATCH] ")


@pytest.mark.parametrize(
    ("source_path", "written", "reason"),
    [
        ("missing\nfile.json", False, "which does not exist."),
        (
            "doc\nsource.json",
            True,
            "a `doc-source` collector output; document type `technical-project` reads a `generator-ready` file, "
            "which the `living-doc-toolkit` command `normalize-docs` writes.",
        ),
    ],
)
def test_a_source_path_with_a_line_break_stays_on_one_line(write_sample, source_path, written, reason):
    # Arrange
    if written:
        write_sample(doc_source.CONTRACT_ID, source_path)

    # Act
    message = _rejection(DocumentType.TECHNICAL_PROJECT, source_path)

    # Assert: the line break is quoted as `\n`, so the message stays one line.
    assert message == f"Input `source-path` is {source_path!r}, {reason}"
    assert "\\n" in message
