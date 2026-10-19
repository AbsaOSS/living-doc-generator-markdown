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

import pytest
from living_doc_utilities.contracts import (
    coverage_matrix,
    doc_entities,
    doc_source,
    generator_ready,
    ui_test_catalog,
    ui_tests,
)
from living_doc_utilities.contracts.compat import installed_utilities_version

from generator_markdown.action_inputs import DocumentType
from generator_markdown.source_reader import (
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
def _unreadable_source(tmp_path, write_sample):
    if os.geteuid() == 0:
        pytest.skip("root reads a file whatever its mode")
    source = write_sample(generator_ready.CONTRACT_ID, SOURCE)
    source.chmod(0o000)
    yield source
    # Readable again, so the `tmp_path` cleanup can remove it.
    source.chmod(0o600)


def _rejection(document_type: DocumentType, source_path: str = SOURCE) -> str:
    with pytest.raises(SourceInputError) as error:
        read_source(document_type, source_path)
    message = str(error.value)
    # Every rejection is the one line the run fails with, naming the input.
    assert message.startswith("Input `source-path` is ")
    assert "\n" not in message
    return message


def test_every_document_type_reads_one_toolkit_contract_written_by_one_toolkit_command():
    # Assert
    assert set(CONTRACT_NAMES) == set(DocumentType)
    assert set(TOOLKIT_COMMANDS) == set(DocumentType)


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
    assert message.startswith("Input `source-path` is 'input.json', which is not JSON: ")


@pytest.mark.parametrize(
    ("content", "detail"),
    [
        ("{}", "schema_version is missing or not a string"),
        ("[]", "schema_version is missing or not a string"),
        ('{"schema_version": 1}', "schema_version is missing or not a string"),
        (
            '{"schema_version": "generator-ready"}',
            "schema_version 'generator-ready' does not match '<contract-name>-v<major>.<minor>.<patch>'",
        ),
    ],
)
def test_a_file_without_a_valid_schema_version_is_rejected_as_an_invalid_contract_id(tmp_path, content, detail):
    # Arrange
    (tmp_path / SOURCE).write_text(content, encoding="utf-8")

    # Act
    message = _rejection(DocumentType.TECHNICAL_PROJECT)

    # Assert
    assert message == (
        f"Input `source-path` is 'input.json', not a valid `generator-ready` file: [INVALID_CONTRACT_ID] {detail}"
    )


def test_a_schema_invalid_file_is_rejected_keeping_the_utilities_pin_hint(write_sample):
    # Arrange: a `generator-ready` file with no `document`, written by another utilities version.
    source = write_sample(generator_ready.CONTRACT_ID, SOURCE)
    payload = json.loads(source.read_text(encoding="utf-8"))
    del payload["document"]
    payload["metadata"]["producer"]["utilities_version"] = "0.0.1"
    source.write_text(json.dumps(payload), encoding="utf-8")

    # Act
    message = _rejection(DocumentType.TECHNICAL_PROJECT)

    # Assert
    assert message == (
        "Input `source-path` is 'input.json', not a valid `generator-ready` file: [SCHEMA_VALIDATION_FAILED] "
        "$: 'document' is a required property (file written by utilities '0.0.1', this is utilities "
        f"'{installed_utilities_version()}'); the components run different utilities versions — align the pins"
    )


def test_a_file_failing_model_validation_is_rejected_on_one_line(write_sample):
    # Arrange: a coverage matrix whose summary no longer matches its rows passes the schema, not the model.
    source = write_sample(coverage_matrix.CONTRACT_ID, SOURCE)
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["summary"]["covered_acs"] += 1
    source.write_text(json.dumps(payload), encoding="utf-8")

    # Act
    with pytest.raises(SourceInputError) as error:
        read_source(DocumentType.COVERAGE_MATRIX, SOURCE)

    # Assert: pydantic's report spans lines; the message the run fails with does not.
    assert "\n" in str(error.value.__cause__)
    message = str(error.value)
    assert message.startswith(
        "Input `source-path` is 'input.json', not a valid `coverage-matrix` file: [SCHEMA_VALIDATION_FAILED] "
        "coverage-matrix-v1.0.0: payload passed schema validation but failed model validation:"
    )
    assert "\n" not in message


def test_a_version_of_the_expected_contract_the_installed_utilities_lacks_is_rejected_with_the_pin_hint(tmp_path):
    # Arrange
    (tmp_path / SOURCE).write_text('{"schema_version": "generator-ready-v9.9.9"}', encoding="utf-8")

    # Act
    message = _rejection(DocumentType.TECHNICAL_PROJECT)

    # Assert
    assert message == (
        f"Input `source-path` is 'input.json', a `generator-ready` version living-doc-utilities "
        f"{installed_utilities_version()} ships no schema for (generator-ready-v9.9.9-schema.json); "
        "the components run different utilities versions — align the pins."
    )


def test_an_unknown_contract_is_rejected_as_a_contract_mismatch(tmp_path):
    # Arrange
    (tmp_path / SOURCE).write_text('{"schema_version": "foo-v1.0.0"}', encoding="utf-8")

    # Act
    message = _rejection(DocumentType.TECHNICAL_PROJECT)

    # Assert
    assert message == (
        "Input `source-path` is 'input.json', not a valid `generator-ready` file: "
        "[CONTRACT_MISMATCH] expected one of ['generator-ready'], got 'foo'"
    )


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
